#!/usr/bin/env bash
# Build (or reuse) the dedicated venv that tools/_venv.py re-execs into when a tool
# needs a third-party module. Idempotent: safe to run again on an existing venv.
#
#   bash tools/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}"
VENV_DIR="$HOME_DIR/venv"

echo "gaspol-video venv: $VENV_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "creating venv..."
  python3 -m venv "$VENV_DIR"
else
  echo "venv already exists, reusing it"
fi

echo "installing requirements..."
"$VENV_DIR/bin/pip" install -r "$ROOT/requirements.txt"

echo "installing Playwright chromium..."
"$VENV_DIR/bin/python" -m playwright install chromium

echo "interpreter: $VENV_DIR/bin/python"
