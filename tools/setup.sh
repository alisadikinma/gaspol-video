#!/usr/bin/env bash
# Build (or reuse) the dedicated venv that tools/_venv.py re-execs into when a tool
# needs a third-party module. Idempotent: safe to run again on an existing venv.
#
#   bash tools/setup.sh
#   PYTHON=/path/to/python3.11 bash tools/setup.sh
#   bash tools/setup.sh --ml     # also build venv-ml and fetch the ML weights (GV-24)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}"
VENV_DIR="$HOME_DIR/venv"
PYTHON="${PYTHON:-python3}"
WITH_ML=0
for arg in "$@"; do
  case "$arg" in
    --ml) WITH_ML=1 ;;
    *) echo "unknown option: $arg (supported: --ml)" >&2; exit 2 ;;
  esac
done

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

# Face detector model for tools/face_box.py (GV-23): OpenCV YuNet from opencv_zoo. Same rule as above: pinned hash.
FACE_MODEL="$MODEL_DIR/face_detection_yunet_2023mar.onnx"
FACE_MODEL_URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
FACE_MODEL_SHA256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
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

if [ "$WITH_ML" = "1" ]; then
  # Separate venv: torch, jax and the SAM 2 / TAPNet checkouts must not leak into the shared venv.
  ML_VENV_DIR="$HOME_DIR/venv-ml"
  PYTHON_ML="${PYTHON_ML:-python3}"
  if [ ! -x "$ML_VENV_DIR/bin/python" ]; then
    resolved="$(command -v "$PYTHON_ML" 2>/dev/null || true)"
    ver="$([ -n "$resolved" ] && python_version_of "$resolved" || true)"
    if [ -z "$resolved" ] || [ -z "$ver" ] || ! version_at_least_3_10 "$ver"; then
      echo "gaspol-video --ml needs Python 3.10+ (found ${ver:-unknown} at ${resolved:-$PYTHON_ML}); set PYTHON_ML=/path/to/python3.10+ and re-run" >&2
      exit 1
    fi
    echo "creating ml venv: $ML_VENV_DIR"
    "$resolved" -m venv "$ML_VENV_DIR"
  else
    ver="$(python_version_of "$ML_VENV_DIR/bin/python" || true)"
    if [ -z "$ver" ] || ! version_at_least_3_10 "$ver"; then
      echo "existing ml venv at $ML_VENV_DIR uses Python ${ver:-unknown} (< 3.10); delete it (rm -rf \"$ML_VENV_DIR\") and re-run tools/setup.sh --ml" >&2
      exit 1
    fi
    echo "ml venv already exists, reusing it"
  fi

  echo "installing ml requirements..."
  # No CUDA build on a Mac; without this the sam2 install tries to compile the CUDA extension.
  export SAM2_BUILD_CUDA=0
  "$ML_VENV_DIR/bin/pip" install -r "$ROOT/requirements-ml.txt"

  # ML weights for tools/vidkit/ml.py. Same rule as the models above: pinned URL and hash.
  fetch_pinned() {
    local dest="$1" url="$2" want="$3"
    if [ -f "$dest" ] && [ "$(shasum -a 256 "$dest" | cut -d' ' -f1)" = "$want" ]; then
      echo "model ok $dest"
      return 0
    fi
    local tmp
    tmp="$(mktemp "$MODEL_DIR/.ml.XXXXXX")"
    FETCH_TMP="$tmp"
    trap 'rm -f "$FETCH_TMP"' EXIT
    trap 'rm -f "$FETCH_TMP"; exit 130' INT
    trap 'rm -f "$FETCH_TMP"; exit 143' TERM
    if ! curl -fSL --connect-timeout 30 --speed-time 60 --speed-limit 1024 --retry 3 -o "$tmp" "$url"; then
      rm -f "$tmp"
      echo "model download failed: $url" >&2
      exit 1
    fi
    local got
    got="$(shasum -a 256 "$tmp" | cut -d' ' -f1)"
    if [ "$got" != "$want" ]; then
      rm -f "$tmp"
      echo "model sha256 mismatch: expected $want got $got" >&2
      exit 1
    fi
    mv "$tmp" "$dest"
    FETCH_TMP=""
    echo "model downloaded $dest"
  }
  fetch_pinned "$MODEL_DIR/tapnextpp_ckpt.pt" \
    "https://storage.googleapis.com/dm-tapnet/tapnextpp/tapnextpp_ckpt.pt" \
    "cb96a43444ccb4fbdb25d800b88c7ba196179a526e78f01b021a16b1c1eff6da"
  fetch_pinned "$MODEL_DIR/sam2.1_hiera_small.pt" \
    "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt" \
    "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"

  echo "ml interpreter: $ML_VENV_DIR/bin/python"
fi

echo "interpreter: $VENV_DIR/bin/python"
