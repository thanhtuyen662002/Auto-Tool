#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

check_command() {
  local command_name="$1"
  local label="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "[READY] $label: $(command -v "$command_name")"
  else
    echo "[MISS ] $label"
    failed=1
  fi
}

echo "Auto Tool local system check"
echo "============================"
check_command python3 "Python 3"
check_command node "Node.js"
check_command npm "npm"
if PYTHONPATH="$ROOT/backend" python3 -c "from app.utils.dependency_manager import find_tool; import sys; p=find_tool('ffmpeg'); print('[READY] FFmpeg: '+str(p) if p else '[MISS ] FFmpeg'); sys.exit(0 if p else 1)"; then :; else failed=1; fi
if PYTHONPATH="$ROOT/backend" python3 -c "from app.utils.dependency_manager import find_tool; import sys; p=find_tool('ffprobe'); print('[READY] ffprobe: '+str(p) if p else '[MISS ] ffprobe'); sys.exit(0 if p else 1)"; then :; else failed=1; fi

if [[ -f "$ROOT/frontend/dist/index.html" ]]; then
  echo "[READY] Frontend build"
else
  echo "[WARN ] Frontend build missing. Run scripts/build_frontend.sh"
fi

exit "$failed"
