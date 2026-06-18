# #!/usr/bin/env bash
# set -euo pipefail

# ROOT="$(cd "$(dirname "$0")" && pwd)"

# echo "╔══════════════════════════════════════╗"
# echo "║     Full-Stack RAG System Setup      ║"
# echo "╚══════════════════════════════════════╝"
# echo ""

# # --- Backend ---
# echo ">>> Setting up backend..."
# VENV_PYTHON="$ROOT/backend/venv/bin/python"
# VENV_PIP="$ROOT/backend/venv/bin/pip"

# if [ ! -f "$VENV_PYTHON" ]; then
#     echo "    Creating Python virtual environment..."
#     python3 -m venv "$ROOT/backend/venv"
# fi
# "$VENV_PIP" install -q -r "$ROOT/backend/requirements.txt" 2>/dev/null
# echo "    Backend dependencies ready."

# # --- Frontend ---
# echo ">>> Setting up frontend..."
# cd "$ROOT/frontend"
# npm install --silent 2>/dev/null
# echo "    Frontend dependencies ready."

# echo ""
# echo "╔══════════════════════════════════════╗"
# echo "║  Starting services                   ║"
# echo "║                                      ║"
# echo "║  API:   http://localhost:8000         ║"
# echo "║  Docs:  http://localhost:8000/docs    ║"
# echo "║  Chat:  http://localhost:5173         ║"
# echo "╚══════════════════════════════════════╝"
# echo ""

# # Ensure Ollama is running (start if not)
# ollama serve &>/dev/null &

# # Start backend in background using venv
# cd "$ROOT/backend" && "$VENV_PYTHON" main.py &
# BACKEND_PID=$!

# # Start frontend
# cd "$ROOT/frontend" && npm run dev &
# FRONTEND_PID=$!

# trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# wait


#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║     Full-Stack RAG System Setup      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- Backend ---
echo ">>> Setting up backend..."
VENV_PYTHON="$ROOT/backend/venv/bin/python"
VENV_PIP="$ROOT/backend/venv/bin/pip"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "    Creating Python virtual environment..."
    python3 -m venv "$ROOT/backend/venv"
fi
"$VENV_PIP" install -q -r "$ROOT/backend/requirements.txt" 2>/dev/null
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

# Start backend in background using venv
cd "$ROOT/backend" && "$VENV_PYTHON" main.py &
BACKEND_PID=$!

# Wait until backend is accepting connections
echo ">>> Waiting for backend to be ready..."
while ! curl -s http://localhost:8000 > /dev/null; do
    sleep 1
done
echo "    Backend is up!"

# Start frontend
cd "$ROOT/frontend" && npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

wait