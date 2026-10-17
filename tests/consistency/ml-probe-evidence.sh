#!/usr/bin/env bash
# GV-24 Phase A: the ML probe record exists and carries every measured field.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
f="docs/evals/ml-probe.md"
[ -f "$f" ] || { echo "FAIL ml-probe.md missing"; exit 1; }
fail=0
for key in python torch mps_available tapnextpp_sha256 sam2_sha256 tapnext_fps sam2_fps licence_tapnet licence_sam2; do
  if ! grep -Eq "^${key}:[[:space:]]*[^[:space:]]+" "$f"; then
    echo "FAIL ml-probe.md key '${key}:' missing or empty"
    fail=1
  fi
done
[ "$fail" -eq 0 ] || exit 1
echo "PASS ml-probe.md has all probe fields"
