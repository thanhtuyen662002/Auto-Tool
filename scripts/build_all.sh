#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

echo "Building Auto Tool Studio..."
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"
bash "$ROOT/scripts/build_frontend.sh"
bash "$ROOT/scripts/check_system.sh"
bash "$ROOT/scripts/check_production_build.sh"
echo "Build completed."
