#!/usr/bin/env bash
# GV-23: setup.sh fetches the face detector model with a pinned hash, so tools/face_box.py
# never runs against an unverified model file.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
need() { if ! grep -qE -- "$1" tools/setup.sh; then echo "FAIL tools/setup.sh: $2"; fail=1; fi; }
need 'face_detector/blaze_face_short_range/float16/1/blaze_face_short_range\.tflite' "no blaze_face_short_range download"
need 'https://storage\.googleapis\.com/mediapipe-models/' "model not fetched from the mediapipe-models bucket"
need 'FACE_MODEL_SHA256="[0-9a-f]{64}"' "no pinned 64-hex FACE_MODEL_SHA256"
exit $fail
