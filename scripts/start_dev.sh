#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi

export AUTO_TOOL_ROOT="$ROOT"
(
  cd "$ROOT/backend"
  "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
backend_pid=$!
(
  cd "$ROOT/frontend"
  npm run dev
) &
frontend_pid=$!

trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
wait
