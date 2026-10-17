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

# Person segmentation model for tools/person_mask.py (GV-17). Versioned URL plus a pinned
# hash: "latest" can change under us, and a swapped model would silently change every mask.
MODEL_DIR="${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}/models"
MODEL="$MODEL_DIR/selfie_segmenter.tflite"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite"
MODEL_SHA256="191ac9529ae506ee0beefa6b2c945a172dab9d07d1e802a290a4e4038226658b"
mkdir -p "$MODEL_DIR"
if [ -f "$MODEL" ] && [ "$(shasum -a 256 "$MODEL" | cut -d' ' -f1)" = "$MODEL_SHA256" ]; then
  echo "model ok $MODEL"
else
  tmp="$(mktemp "$MODEL_DIR/.selfie.XXXXXX")"
  if ! curl -fsSL -o "$tmp" "$MODEL_URL"; then
    rm -f "$tmp"
    echo "model download failed: $MODEL_URL" >&2
    exit 1
  fi
  got="$(shasum -a 256 "$tmp" | cut -d' ' -f1)"
  if [ "$got" != "$MODEL_SHA256" ]; then
    rm -f "$tmp"
    echo "model sha256 mismatch: expected $MODEL_SHA256 got $got" >&2
    exit 1
  fi
  mv "$tmp" "$MODEL"
  echo "model downloaded $MODEL"
fi

# Face detector model for tools/face_box.py (GV-23). Same rule as above: versioned URL, pinned hash.
FACE_MODEL="$MODEL_DIR/blaze_face_short_range.tflite"
FACE_MODEL_URL="https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
FACE_MODEL_SHA256="b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"
if [ -f "$FACE_MODEL" ] && [ "$(shasum -a 256 "$FACE_MODEL" | cut -d' ' -f1)" = "$FACE_MODEL_SHA256" ]; then
  echo "model ok $FACE_MODEL"
else
  tmp="$(mktemp "$MODEL_DIR/.face.XXXXXX")"
  if ! curl -fsSL -o "$tmp" "$FACE_MODEL_URL"; then
    rm -f "$tmp"
    echo "model download failed: $FACE_MODEL_URL" >&2
    exit 1
  fi
  got="$(shasum -a 256 "$tmp" | cut -d' ' -f1)"
  if [ "$got" != "$FACE_MODEL_SHA256" ]; then
    rm -f "$tmp"
    echo "model sha256 mismatch: expected $FACE_MODEL_SHA256 got $got" >&2
    exit 1
  fi
  mv "$tmp" "$FACE_MODEL"
  echo "model downloaded $FACE_MODEL"
fi

echo "interpreter: $VENV_DIR/bin/python"
