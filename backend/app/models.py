from typing import Optional

from sqlmodel import Field, SQLModel


class SessionInDB(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    name: str
    created_at: str
    filenames: str = Field(default="[]")


class MessageInDB(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    role: str
    content: str
    timestamp: str
    sources: Optional[str] = Field(default=None)
