#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

check_path() {
  if [[ -e "$1" ]]; then
    echo "[OK] $2"
  else
    echo "[FAIL] $3"
    failed=1
  fi
}

check_path "$ROOT/frontend/dist" "frontend/dist found" "frontend/dist missing"
check_path "$ROOT/frontend/dist/index.html" "index.html found" "index.html missing"
check_path "$ROOT/frontend/dist/assets" "assets folder found" "assets folder missing"

python_cmd="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  python_cmd="$ROOT/.venv/bin/python"
fi
if PYTHONPATH="$ROOT/backend" "$python_cmd" -c "from app.main import app; assert app is not None"; then
  echo "[OK] backend app import success"
else
  echo "[FAIL] backend app import failed"
  failed=1
fi

if grep -Fxq "VITE_API_BASE_URL=/api" "$ROOT/frontend/.env.production"; then
  echo "[OK] production API base URL is /api"
else
  echo "[FAIL] production API base URL is not /api"
  failed=1
fi

exit "$failed"
