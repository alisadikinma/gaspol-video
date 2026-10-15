#!/usr/bin/env bash
# GV-17: the venv carries mediapipe and setup.sh fetches the selfie segmenter model with a
# pinned hash, so tools/person_mask.py never runs against an unverified model file.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
grep -qE '^mediapipe==' requirements.txt || { echo "FAIL requirements.txt lacks mediapipe"; fail=1; }
need() { if ! grep -qE -- "$1" tools/setup.sh; then echo "FAIL tools/setup.sh: $2"; fail=1; fi; }
need 'selfie_segmenter\.tflite' "no selfie_segmenter.tflite download"
need '[0-9a-f]{64}' "no pinned sha256 for the model"
need 'shasum -a 256' "model hash is not verified"
need 'GASPOL_VIDEO_HOME:-\$HOME/\.gaspol-video\}/models' "model not stored under the gaspol-video home"
exit $fail
