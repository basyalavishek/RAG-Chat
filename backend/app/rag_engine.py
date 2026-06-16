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

from .config import settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the question based on the provided context.

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
        self._load_sessions()

    def _load_sessions(self):
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
        logger.info(f"Created session {sid}")
        return session

    def rename_session(self, session_id: str, name: str) -> bool:
        if session_id not in self._sessions:
            return False
        self._sessions[session_id]["name"] = name
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
        del self._sessions[session_id]
        logger.info(f"Deleted session {session_id}")
        return True

    def ingest_file(self, file_path: str, session_id: str | None = None,
                     original_filename: str | None = None) -> int:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext in (".txt", ".md", ".rst"):
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        docs = loader.load()
        chunks = self.text_splitter.split_documents(docs)
        sid = session_id or DEFAULT_SESSION
        for c in chunks:
            c.metadata["session_id"] = sid
        ids = self.vector_store.add_documents(chunks)
        logger.info(f"Ingested {file_path} into session {sid}: {len(chunks)} chunks")
        if sid in self._sessions:
            display = original_filename or os.path.basename(file_path)
            if display not in self._sessions[sid]["filenames"]:
                self._sessions[sid]["filenames"].append(display)
                if self._sessions[sid]["name"].startswith("Chat "):
                    clean = os.path.splitext(display)[0][:30]
                    self._sessions[sid]["name"] = clean
        return len(chunks)

    def retrieve(self, query: str, k: int | None = None,
                 session_id: str | None = None) -> list[Document]:
        k = k or settings.top_k
        filt = self._session_filter(session_id)
        return self.vector_store.similarity_search(query, k=k, filter=filt)

    def answer(self, query: str, session_id: str | None = None) -> dict:
        docs = self.retrieve(query, session_id=session_id)
        context = "\n\n".join(d.page_content for d in docs)

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm
        response = chain.invoke({"context": context, "question": query})

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
        docs = self.retrieve(query, session_id=session_id)
        context = "\n\n".join(d.page_content for d in docs)

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm

        async for chunk in chain.astream({"context": context, "question": query}):
            yield chunk.content

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
