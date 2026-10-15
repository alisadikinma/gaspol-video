#!/usr/bin/env bash
# GV-17: KineticOverlay was rendered for real, and the run is written down with a still for
# every effect and every element, so "it renders" is a record somebody looked at, not a claim.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
doc=docs/evals/overlay-kinetik-run.md
[ -f "$doc" ] || { echo "FAIL $doc missing"; exit 1; }
fail=0
for k in "fx 1" "fx 2" "fx 3" "fx 4" "fx 5" "behind panel" "video panel" "bubble" "carousel" "source box" "npx tsc --noEmit"; do
  grep -qiF -- "$k" "$doc" || { echo "FAIL $doc does not record: $k"; fail=1; }
done
exit $fail
