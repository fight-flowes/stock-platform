#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

python -m py_compile $(find "$ROOT_DIR/backend" -name '*.py' -not -path '*/__pycache__/*')

cd "$ROOT_DIR/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
npm run build
