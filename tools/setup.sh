#!/usr/bin/env bash
# Build (or reuse) the dedicated venv that tools/_venv.py re-execs into when a tool
# needs a third-party module. Idempotent: safe to run again on an existing venv.
#
#   bash tools/setup.sh
#   PYTHON=/path/to/python3.11 bash tools/setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}"
VENV_DIR="$HOME_DIR/venv"
PYTHON="${PYTHON:-python3}"

# Prints "3.11" (or nothing, with a nonzero exit, if `$1` cannot be run at all).
python_version_of() {
  "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null
}

# True (exit 0) when "3.11" etc is >= 3.10.
version_at_least_3_10() {
  local major="${1%%.*}" minor="${1##*.}"
  [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }
}

echo "gaspol-video venv: $VENV_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  resolved="$(command -v "$PYTHON" 2>/dev/null || true)"
  ver="$([ -n "$resolved" ] && python_version_of "$resolved" || true)"
  if [ -z "$resolved" ] || [ -z "$ver" ] || ! version_at_least_3_10 "$ver"; then
    echo "gaspol-video needs Python 3.10+ (found ${ver:-unknown} at ${resolved:-$PYTHON}); set PYTHON=/path/to/python3.10+ and re-run" >&2
    exit 1
  fi
  echo "creating venv..."
  "$resolved" -m venv "$VENV_DIR"
else
  ver="$(python_version_of "$VENV_DIR/bin/python" || true)"
  if [ -z "$ver" ] || ! version_at_least_3_10 "$ver"; then
    echo "existing venv at $VENV_DIR uses Python ${ver:-unknown} (< 3.10); delete it (rm -rf \"$VENV_DIR\") and re-run tools/setup.sh to rebuild with a newer Python" >&2
    exit 1
  fi
  echo "venv already exists, reusing it"
fi

echo "installing requirements..."
"$VENV_DIR/bin/pip" install -r "$ROOT/requirements.txt"

echo "installing Playwright chromium..."
"$VENV_DIR/bin/python" -m playwright install chromium

echo "interpreter: $VENV_DIR/bin/python"
