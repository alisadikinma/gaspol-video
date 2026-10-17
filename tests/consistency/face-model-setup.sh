#!/usr/bin/env bash
# GV-23: setup.sh fetches the OpenCV YuNet face model with a pinned hash, so tools/face_box.py
# never runs against an unverified model file. The MediaPipe face detector is gone (it aborts
# on Metal) and its pin must not linger.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
need() { if ! grep -qE -- "$1" tools/setup.sh; then echo "FAIL tools/setup.sh: $2"; fail=1; fi; }
need 'models/face_detection_yunet/face_detection_yunet_2023mar\.onnx' "no YuNet onnx download"
need 'github\.com/opencv/opencv_zoo/' "model not fetched from opencv_zoo"
need 'FACE_MODEL_SHA256="[0-9a-f]{64}"' "no pinned 64-hex FACE_MODEL_SHA256"
if grep -q 'blaze_face' tools/setup.sh; then echo "FAIL tools/setup.sh: blaze_face block still present"; fail=1; fi
grep -qE '^opencv-contrib-python==5\.0\.0\.93' requirements.txt || { echo "FAIL requirements.txt lacks opencv-contrib-python==5.0.0.93"; fail=1; }
exit $fail
