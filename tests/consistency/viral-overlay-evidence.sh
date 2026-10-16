#!/usr/bin/env bash
# GV-19 Phase B: the viral overlay vocabulary was rendered for real and the run is written down,
# one heading per element, so "it renders" is a record somebody looked at, not a claim.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
doc=docs/evals/viral-overlay-run.md
[ -f "$doc" ] || { echo "FAIL $doc missing"; exit 1; }
fail=0
for k in "sticker icon" "step counter" "red vignette" "falling burst" "two-tier preset" "center anchor" "npx tsc --noEmit"; do
  grep -qiF -- "$k" "$doc" || { echo "FAIL $doc does not record: $k"; fail=1; }
done
exit $fail
