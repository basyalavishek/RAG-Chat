import os
import logging
import warnings
from contextlib import asynccontextmanager

# Suppress noisy warnings from langchain/pytorch/chromadb
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["CHROMA_SKIP_TELEMETRY"] = "true"
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
warnings.filterwarnings("ignore", category=UserWarning, message=".*CUDA initialization.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*model_fields.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*chromadb.*")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("chromadb.segment.impl.manager").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG engine...")
    from app.rag_engine import engine
    yield
    logger.info("Shutting down...")


app = FastAPI(title="RAG API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
