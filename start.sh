#!/usr/bin/env bash
# RideShield — one-command run.
# Creates the venv on first use, installs dependencies, starts uvicorn.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[start] creating virtualenv (.venv) and installing dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

echo "[start] RideShield on http://localhost:${PORT:-8000}"
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
