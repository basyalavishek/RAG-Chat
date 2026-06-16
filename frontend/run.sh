#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing Node dependencies ==="
npm install
echo ""
echo "=== Starting frontend on http://localhost:5173 ==="
npm run dev
