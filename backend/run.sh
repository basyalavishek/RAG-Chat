#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt
echo ""
echo "=== Starting RAG API on http://localhost:8000 ==="
python main.py
