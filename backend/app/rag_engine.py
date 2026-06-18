import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from sqlmodel import Session, select, delete

from .config import settings
from .database import engine as db_engine, init_db
from .models import SessionInDB, MessageInDB

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the question based on the provided context and conversation history.

Conversation History:
{history}

Context:
{context}

Question:
{question}

Answer the question concisely and accurately. If the context doesn't contain enough information, say so.
"""

DEFAULT_SESSION = "default"


class RAGEngine:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model
        )
        self.vector_store = Chroma(
            persist_directory=settings.chroma_persist_dir,
            embedding_function=self.embeddings,
            collection_name="documents",
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        self._llm = None
        self._sessions: dict[str, dict] = {}
        self._messages: dict[str, list[dict]] = {}
        self._saved_message_ids: set[str] = set()
        self._init_db()
        self._load_sessions()
        self._load_messages()

    def _init_db(self):
        init_db()

    def _save_sessions(self):
        with Session(db_engine) as session:
            for sid, s in self._sessions.items():
                db_session = SessionInDB(
                    id=sid,
                    name=s["name"],
                    created_at=s["created_at"],
                    filenames=json.dumps(s["filenames"]),
                )
                session.merge(db_session)
            session.commit()

    def _load_sessions(self):
        with Session(db_engine) as session:
            rows = session.exec(select(SessionInDB)).all()
            for row in rows:
                self._sessions[row.id] = {
                    "id": row.id,
                    "name": row.name,
                    "created_at": row.created_at,
                    "filenames": json.loads(row.filenames),
                }

        all_meta = self.vector_store._collection.get(include=["metadatas"])
        seen = set()
        for m in all_meta["metadatas"] or []:
            sid = (m or {}).get("session_id", DEFAULT_SESSION)
            if sid not in seen:
                seen.add(sid)
                self._sessions.setdefault(sid, {
                    "id": sid,
                    "name": DEFAULT_SESSION if sid == DEFAULT_SESSION else f"Chat {sid[:8]}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "filenames": [],
                })
        for m in all_meta["metadatas"] or []:
            sid = (m or {}).get("session_id", DEFAULT_SESSION)
            src = (m or {}).get("source", "")
            if src and src not in self._sessions[sid]["filenames"]:
                fname = os.path.basename(src)
                self._sessions[sid]["filenames"].append(fname)
                if self._sessions[sid]["name"] in (DEFAULT_SESSION, f"Chat {sid[:8]}"):
                    clean = os.path.splitext(fname)[0][:30]
                    self._sessions[sid]["name"] = clean
        self._save_sessions()

    def _load_messages(self):
        with Session(db_engine) as session:
            rows = session.exec(
                select(MessageInDB).order_by(MessageInDB.timestamp)
            ).all()
            for row in rows:
                msg = {
                    "id": row.id,
                    "role": row.role,
                    "content": row.content,
                    "timestamp": row.timestamp,
                }
                if row.sources:
                    msg["sources"] = json.loads(row.sources)
                self._messages.setdefault(row.session_id, []).append(msg)
                self._saved_message_ids.add(row.id)

    def _save_messages(self):
        with Session(db_engine) as session:
            for sid, msgs in self._messages.items():
                for msg in msgs:
                    if msg["id"] in self._saved_message_ids:
                        continue
                    db_msg = MessageInDB(
                        id=msg["id"],
                        session_id=sid,
                        role=msg["role"],
                        content=msg["content"],
                        timestamp=msg["timestamp"],
                        sources=json.dumps(msg.get("sources")) if msg.get("sources") else None,
                    )
                    session.add(db_msg)
                    self._saved_message_ids.add(msg["id"])
            session.commit()

    def _build_history(self, session_id: str | None) -> str:
        if not session_id:
            return ""
        msgs = self._messages.get(session_id, [])
        lines = []
        for msg in msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    @property  # @property decorator lets you treat a class method like a regular variable attribute.
    def llm(self):
        if self._llm is not None:
            return self._llm
        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.3,
            )
        else:
            from langchain_community.chat_models import ChatOllama
            self._llm = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0.3,
            )
        return self._llm

    def _session_filter(self, session_id: str | None) -> dict | None:
        if session_id is None:
            return None
        return {"session_id": session_id}

    def create_session(self, name: str | None = None) -> dict:
        sid = uuid.uuid4().hex[:12]
        session = {
            "id": sid,
            "name": name or f"Chat {sid[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filenames": [],
        }
        self._sessions[sid] = session
        self._messages[sid] = []
        self._save_sessions()
        logger.info(f"Created session {sid}")
        return session

    def rename_session(self, session_id: str, name: str) -> bool:
        if session_id not in self._sessions:
            return False
        self._sessions[session_id]["name"] = name
        self._save_sessions()
        logger.info(f"Renamed session {session_id} -> {name}")
        return True

    def list_sessions(self) -> list[dict]:
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        self.clear(session_id=session_id)
        msgs = self._messages.pop(session_id, [])
        with Session(db_engine) as session:
            session.exec(
                delete(MessageInDB).where(MessageInDB.session_id == session_id)
            )
            session.exec(
                delete(SessionInDB).where(SessionInDB.id == session_id)
            )
            session.commit()
        for msg in msgs:
            self._saved_message_ids.discard(msg["id"])
        del self._sessions[session_id]
        self._save_sessions()
        logger.info(f"Deleted session {session_id}")
        return True

    def get_messages(self, session_id: str) -> list[dict]:
        return self._messages.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str,
                    sources: list | None = None) -> dict:
        msg = {
            "id": uuid.uuid4().hex[:12],
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if sources:
            msg["sources"] = sources
        self._messages.setdefault(session_id, []).append(msg)
        self._save_messages()
        return msg


# Data Processing Pipeline
    def ingest_file(self, file_path: str, session_id: str | None = None,
                     original_filename: str | None = None) -> int:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            loader = PyPDFLoader(file_path) # specialized loader to extract text and structure from PDF files.
        elif ext in (".txt", ".md", ".rst"):
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        docs = loader.load() #  reads the text out of the file from your hard drive.
        chunks = self.text_splitter.split_documents(docs) # splits the text into smaller chunks.
        sid = session_id or DEFAULT_SESSION
        for c in chunks:
            c.metadata["session_id"] = sid
        ids = self.vector_store.add_documents(chunks) # embedding vectors and stores them in Chroma
        logger.info(f"Ingested {file_path} into session {sid}: {len(chunks)} chunks")
        if sid in self._sessions:
            display = original_filename or os.path.basename(file_path)
            if display not in self._sessions[sid]["filenames"]:
                self._sessions[sid]["filenames"].append(display)
                if self._sessions[sid]["name"].startswith("Chat "):
                    clean = os.path.splitext(display)[0][:30]
                    self._sessions[sid]["name"] = clean
                self._save_sessions()
        return len(chunks)

# The search engine of this RAG application
    def retrieve(self, query: str, k: int | None = None,
                 session_id: str | None = None) -> list[Document]:
        k = k or settings.top_k
        filt = self._session_filter(session_id)
        return self.vector_store.similarity_search(query, k=k, filter=filt)

# all answer by llm at once
    def answer(self, query: str, session_id: str | None = None) -> dict:
        docs = self.retrieve(query, session_id=session_id)
        context = "\n\n".join(d.page_content for d in docs)
        history = self._build_history(session_id)

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm
        response = chain.invoke({"history": history, "context": context, "question": query})

        sources = [
            {
                "content": d.page_content[:500],
                "source": d.metadata.get("source", "unknown"),
                "page": d.metadata.get("page"),
            }
            for d in docs
        ]

        return {
            "answer": response.content,
            "sources": sources,
        }


# answers in stream mode (Generator function : A function that use 'yield' to return values)
    async def answer_stream(self, query: str,
                            session_id: str | None = None) -> AsyncGenerator[str, None]:
        docs = self.retrieve(query, session_id=session_id) # fetches relevant documents from Chroma
        context = "\n\n".join(d.page_content for d in docs) # concatenate them into a single context string.
        history = self._build_history(session_id)

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm

        async for chunk in chain.astream({"history": history, "context": context, "question": query}):
            yield chunk.content

# counts the number of chunks in a specific session
    def get_document_count(self, session_id: str | None = None) -> int:
        if session_id is None:
            return self.vector_store._collection.count()
        filt = self._session_filter(session_id)
        result = self.vector_store._collection.get(where=filt)
        return len(result["ids"]) if result and result["ids"] else 0


# removes all chunks from a specific session
    def clear(self, session_id: str | None = None) -> None:
        if session_id is None:
            docs = self.vector_store._collection.get()["ids"]
            if docs:
                self.vector_store._collection.delete(docs)
            logger.info("Cleared all documents from vector store")
        else:
            filt = self._session_filter(session_id)
            result = self.vector_store._collection.get(where=filt)
            ids = result["ids"] if result and result["ids"] else []
            if ids:
                self.vector_store._collection.delete(ids)
            logger.info(f"Cleared session {session_id}: {len(ids)} chunks deleted")


engine = RAGEngine()
