# RAG Chat

A chat app with RAG (Retrieval-Augmented Generation) using Ollama LLMs. Each chat session has its own set of documents — upload PDFs/TXT files and ask questions about them.

## How it works

1. Upload a document (PDF or TXT) to a chat session
2. The file is split into chunks and stored in a vector database (ChromaDB)
3. Ask a question — relevant chunks are retrieved and sent to the LLM as context
4. The LLM answers based on your documents

## Tech

- **Backend**: Python, FastAPI, LangChain, ChromaDB, HuggingFace embeddings
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **LLM**: Ollama (llama3.2:1b)

## Setup

```bash
./start.sh
```

This installs dependencies and starts both backend (port 8000) and frontend (port 5173).

## Known issues

- First query after starting the server takes ~30 seconds (model loads into memory)
- Runs on CPU only (old NVIDIA driver, no GPU acceleration)
- ChromaDB telemetry errors in logs are harmless

## Notes

Built with OpenCode (AI-assisted coding tool).
