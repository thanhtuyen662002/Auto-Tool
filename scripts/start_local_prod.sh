#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

echo "Starting Auto Tool Studio Production Local Server..."

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"

if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  echo "Frontend build not found. Building frontend..."
  bash "$ROOT/scripts/build_frontend.sh"
fi

bash "$ROOT/scripts/check_production_build.sh"

export AUTO_TOOL_ROOT="$ROOT"
export AUTO_TOOL_PORT=8000
export AUTO_TOOL_STRICT_PORT=1
cd "$ROOT/backend"
exec "$VENV/bin/python" -m app.launcher
