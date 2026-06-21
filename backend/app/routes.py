import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse # StreamingResponse handles real-time data streaming (like ChatGPT typing out an answer).

from pydantic import BaseModel

from .config import settings
from .rag_engine import engine

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    sources: list


class PatchSessionRequest(BaseModel):
    name: str | None = None


class AddMessageRequest(BaseModel):
    role: str
    content: str
    sources: list | None = None


# --- Legacy endpoints (default session) ---

@router.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".txt", ".md", ".rst"):
        raise HTTPException(
            400, f"Unsupported file type: {ext}. Use PDF, TXT, MD, or RST."
        )

    dest = os.path.join(settings.upload_dir, f"{uuid.uuid4()}{ext}")
    with open(dest, "wb") as f:
        f.write(await file.read())

    task_id = engine.start_ingest(dest, original_filename=file.filename)
    return {"task_id": task_id, "filename": file.filename}


@router.get("/ingest/task/{task_id}")
async def get_ingest_task(task_id: str):
    task = engine.get_ingest_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest):
    if engine.get_document_count() == 0:
        raise HTTPException(400, "No documents ingested yet. Upload documents first.")
    return engine.answer(body.query)


@router.post("/query/stream")
async def query_stream(body: QueryRequest):
    if engine.get_document_count() == 0:
        raise HTTPException(400, "No documents ingested yet. Upload documents first.")
    return StreamingResponse(
        engine.answer_stream(body.query),
        media_type="text/event-stream",
    )


@router.get("/stats")
async def stats():
    return {"total_documents": engine.get_document_count()}


@router.delete("/clear")
async def clear():
    engine.clear()
    return {"message": "All documents cleared"}


# --- Session-based endpoints ---

@router.post("/sessions")
async def create_session():
    session = engine.create_session()
    return session


@router.get("/sessions")
async def list_sessions():
    return engine.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.patch("/sessions/{session_id}") # update
async def patch_session(session_id: str, body: PatchSessionRequest):
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if body.name:
        engine.rename_session(session_id, body.name)
    return engine.get_session(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not engine.delete_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"message": "Session deleted"}


## allows a user to upload a file into a specific, isolated chat session instead of adding it to the global, default workspace.

@router.post("/sessions/{session_id}/ingest")
async def session_ingest(session_id: str, file: UploadFile = File(...)):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".txt", ".md", ".rst"):
        raise HTTPException(
            400, f"Unsupported file type: {ext}. Use PDF, TXT, MD, or RST."
        )

    dest = os.path.join(settings.upload_dir, f"{uuid.uuid4()}{ext}")
    with open(dest, "wb") as f:
        f.write(await file.read())

    task_id = engine.start_ingest(dest, session_id=session_id,
                                   original_filename=file.filename)
    return {"task_id": task_id, "filename": file.filename}

# handle asking questions (querying) inside a specific, isolated chat session.
@router.post("/sessions/{session_id}/query")
async def session_query(session_id: str, body: QueryRequest):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    if engine.get_document_count(session_id=session_id) == 0:
        raise HTTPException(400, "No documents in this session. Upload documents first.")
    return engine.answer(body.query, session_id=session_id)


@router.post("/sessions/{session_id}/query/stream")
async def session_query_stream(session_id: str, body: QueryRequest):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    if engine.get_document_count(session_id=session_id) == 0:
        raise HTTPException(400, "No documents in this session. Upload documents first.")
    return StreamingResponse(
        engine.answer_stream(body.query, session_id=session_id),
        media_type="text/event-stream",
    )


@router.get("/sessions/{session_id}/stats")
async def session_stats(session_id: str):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"total_documents": engine.get_document_count(session_id=session_id)}


@router.post("/sessions/{session_id}/clear")
async def session_clear(session_id: str):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    engine.clear(session_id=session_id)
    return {"message": f"Session {session_id} documents cleared"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    return engine.get_messages(session_id)


@router.post("/sessions/{session_id}/messages")
async def add_session_message(session_id: str, body: AddMessageRequest):
    if not engine.get_session(session_id):
        raise HTTPException(404, "Session not found")
    msg = engine.add_message(session_id, body.role, body.content, body.sources)
    return msg
