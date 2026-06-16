#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║     Full-Stack RAG System Setup      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- Backend ---
echo ">>> Setting up backend..."
cd "$ROOT/backend"
pip3 install -q -r requirements.txt 2>/dev/null
echo "    Backend dependencies ready."

# --- Frontend ---
echo ">>> Setting up frontend..."
cd "$ROOT/frontend"
npm install --silent 2>/dev/null
echo "    Frontend dependencies ready."

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Starting services                   ║"
echo "║                                      ║"
echo "║  API:   http://localhost:8000         ║"
echo "║  Docs:  http://localhost:8000/docs    ║"
echo "║  Chat:  http://localhost:5173         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Ensure Ollama is running (start if not)
ollama serve &>/dev/null &

# Start backend in background
cd "$ROOT/backend" && python3 main.py &
BACKEND_PID=$!

# Start frontend
cd "$ROOT/frontend" && npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

wait
