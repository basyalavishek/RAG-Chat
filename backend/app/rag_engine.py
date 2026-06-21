
import json
import os
import uuid
import logging
import concurrent.futures
from datetime import datetime, timezone
from typing import AsyncGenerator

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
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

Context (sources are numbered in brackets):
{context}

Question:
{question}

Instructions:
- Answer concisely and accurately.
- When you use information from a specific source, cite it using its bracketed number (e.g., [1], [2]).
- If the context doesn't contain enough information, say so.
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
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._tasks: dict[str, dict] = {}
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
        # FIX 1: Truncate history to the last 6 messages (3 turns) to prevent context explosion
        msgs = self._messages.get(session_id, [])[-6:]
        lines = []
        for msg in msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    @property  
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
            # FIX 2: Switched to the updated langchain_ollama package 
            # and explicitly set num_ctx to 8192 to prevent local context drops
            from langchain_ollama import ChatOllama
            self._llm = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0.1,  # Tighter control over creative hallucinations
                num_ctx=8192,
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

    def ingest_file(self, file_path: str, session_id: str | None = None,
                     original_filename: str | None = None,
                     progress_callback: callable | None = None) -> int:
        if progress_callback:
            progress_callback(5, "loading", "Loading file...")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            loader = PyMuPDFLoader(file_path)
        elif ext in (".txt", ".md", ".rst"):
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        docs = loader.load()

        if progress_callback:
            progress_callback(40, "chunking", "Splitting into chunks...")

        chunks = self.text_splitter.split_documents(docs)
        sid = session_id or DEFAULT_SESSION
        for c in chunks:
            c.metadata["session_id"] = sid

        if progress_callback:
            progress_callback(50, "embedding", f"Embedding {len(chunks)} chunks...")

        ids = self.vector_store.add_documents(chunks) # generate and save  embeddings to vector store

        if progress_callback:
            progress_callback(90, "saving", "Saving session...")

        logger.info(f"Ingested {file_path} into session {sid}: {len(chunks)} chunks")
        if sid in self._sessions:
            display = original_filename or os.path.basename(file_path)
            if display not in self._sessions[sid]["filenames"]:
                self._sessions[sid]["filenames"].append(display)
                if self._sessions[sid]["name"].startswith("Chat "):
                    clean = os.path.splitext(display)[0][:30]
                    self._sessions[sid]["name"] = clean
                self._save_sessions()

        if progress_callback:
            progress_callback(100, "done", f"Indexed {len(chunks)} chunks")

        return len(chunks)

    def start_ingest(self, file_path: str, session_id: str | None = None,
                      original_filename: str | None = None) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = {
            "status": "pending",
            "progress": 0,
            "step": "queued",
            "message": "Queued...",
        }

        def _run():
            try:
                def progress(p, s, m):
                    if task_id in self._tasks:
                        self._tasks[task_id].update({"progress": p, "step": s, "message": m})

                self._tasks[task_id]["status"] = "processing"
                chunks = self.ingest_file(file_path, session_id, original_filename,
                                           progress_callback=progress)
                self._tasks[task_id].update(status="completed", chunks=chunks,
                                             message=f"Indexed {chunks} chunks")
            except Exception as e:
                logger.exception(f"Background ingest {task_id} failed")
                if task_id in self._tasks:
                    self._tasks[task_id].update(status="failed", message=str(e))

        self._executor.submit(_run)
        return task_id

    def get_ingest_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    def retrieve(self, query: str, k: int | None = None,
                 session_id: str | None = None) -> list[Document]:
        k = k or settings.top_k
        filt = self._session_filter(session_id)
        return self.vector_store.similarity_search(query, k=k, filter=filt)

    def _get_standalone_query(self, query: str, history: str) -> str:
        # FIX 3: Internal helper to rewrite follow-up queries so the retriever doesn't fetch garbage.
        if not history:
            return query
            
        condense_prompt = ChatPromptTemplate.from_template(
            "Given the conversation history and a follow-up question, rephrase the follow-up "
            "question into a standalone question for a vector database search.\n\n"
            "History:\n{history}\n\n"
            "Follow-up Question: {query}\n\n"
            "Standalone Question (Output only the clean question text):"
        )
        chain = condense_prompt | self.llm
        response = chain.invoke({"history": history, "query": query})
        return response.content.strip()

    def answer(self, query: str, session_id: str | None = None) -> dict:
        history = self._build_history(session_id)
        
        # Rewrite query contextually before matching vectors
        search_query = self._get_standalone_query(query, history)
        
        docs = self.retrieve(search_query, session_id=session_id)
        context = "\n\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(docs))

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

    async def answer_stream(self, query: str,
                            session_id: str | None = None) -> AsyncGenerator[str, None]:
        history = self._build_history(session_id)
        
        # Rewrite query contextually before matching vectors
        search_query = self._get_standalone_query(query, history)
        
        docs = self.retrieve(search_query, session_id=session_id)
        context = "\n\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(docs))

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm

        async for chunk in chain.astream({"history": history, "context": context, "question": query}):
            yield f"data: {json.dumps({'t': chunk.content})}\n\n"

        sources = [
            {
                "content": d.page_content[:500],
                "source": d.metadata.get("source", "unknown"),
                "page": d.metadata.get("page"),
            }
            for d in docs
        ]
        yield f"data: {json.dumps({'s': sources})}\n\n"
        yield "data: [DONE]\n\n"

    def get_document_count(self, session_id: str | None = None) -> int:
        if session_id is None:
            return self.vector_store._collection.count()
        filt = self._session_filter(session_id)
        result = self.vector_store._collection.get(where=filt)
        return len(result["ids"]) if result and result["ids"] else 0

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