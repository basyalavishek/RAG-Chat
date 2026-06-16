import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    # Ollama
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")

    # OpenAI
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Embeddings
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Chunking
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # Retrieval
    top_k: int = int(os.getenv("TOP_K", "4"))

    # Paths
    chroma_persist_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "chroma"
    )
    upload_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "uploads"
    )


settings = Settings()
os.makedirs(settings.chroma_persist_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
