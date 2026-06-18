import os

from sqlmodel import SQLModel, Session, create_engine, text

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "rag.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with Session(engine) as session:
        session.exec(text("PRAGMA journal_mode=WAL"))
        session.commit()
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
