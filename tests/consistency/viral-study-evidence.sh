#!/usr/bin/env bash
# GV-19 Phase A: the study is written down with numbers, and each claim is tagged data or interpretation.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
doc=docs/evals/viral-audio-study.md
[ -f "$doc" ] || { echo "FAIL $doc missing"; exit 1; }
fail=0
for k in "data" "interpretation" "Findings" "What this changes in phases B, C, D" "not measured"; do
  grep -qF -- "$k" "$doc" || { echo "FAIL $doc does not record: $k"; fail=1; }
done
exit $fail
