#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v npm >/dev/null 2>&1 || { echo "[ERROR] npm was not found. Install Node.js LTS."; exit 1; }

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run build
