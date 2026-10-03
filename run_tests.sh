#!/usr/bin/env bash
# RideShield — run the test suite.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x .venv/bin/pytest ]; then
  echo "[test] .venv missing or incomplete — run ./start.sh once first" >&2
  exit 1
fi

exec .venv/bin/pytest -q
