#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  bash "$ROOT/scripts/build_frontend.sh"
fi
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"
export AUTO_TOOL_ROOT="$ROOT"
cd "$ROOT/backend"
exec "$VENV/bin/python" -m app.launcher
