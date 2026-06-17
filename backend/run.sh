#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$ROOT/venv/bin/python"
VENV_PIP="$ROOT/venv/bin/pip"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$ROOT/venv"
fi

echo "=== Installing Python dependencies ==="
"$VENV_PIP" install -r "$ROOT/requirements.txt"
echo ""
echo "=== Starting RAG API on http://localhost:8000 ==="
"$VENV_PYTHON" main.py
