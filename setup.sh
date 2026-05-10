#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_NODE_BIN="$ROOT_DIR/.tools/node/bin"

if [ -d "$LOCAL_NODE_BIN" ]; then
  export PATH="$LOCAL_NODE_BIN:$PATH"
fi

echo "Setting up Synapse..."

cd "$ROOT_DIR"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

if command -v npm >/dev/null 2>&1; then
  cd "$ROOT_DIR/frontend"
  npm install
else
  echo "npm was not found. Backend setup completed; install Node.js 18+ to set up the frontend."
fi

echo "Done."
