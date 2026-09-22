#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

printf 'Starting backend on http://localhost:8002\n'
(
  cd "$ROOT/backend"
  python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
) &
BACKEND_PID=$!

printf 'Starting frontend on http://localhost:5173\n'
(
  cd "$ROOT/frontend"
  npm run dev
) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM EXIT
wait
