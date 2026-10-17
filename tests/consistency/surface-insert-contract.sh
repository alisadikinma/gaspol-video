#!/usr/bin/env bash
# GV-24 docs contract: green-screen prompt rule, validator check V17, both routes,
# and one docs/debugging.md row per refusal message of screen-insert / embroider.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() { # need <file> <needle> <message>
  if ! grep -qF -- "$2" "$1"; then
    echo "FAIL $3"
    fail=1
  fi
}

need skills/video-gen/SKILL.md "flat solid chroma green screen" "missing green-screen rule"
need skills/video-gen/SKILL.md "insert: green" "missing insert: green note in video-gen"
need skills/video-validate/SKILL.md "Check V17" "missing V17 check in video-validate"
need agents/video-prompt-reviewer.md "### V17." "missing V17 check in video-prompt-reviewer"
need docs/tool-routing.md "screen-insert" "missing screen-insert route in tool-routing"
need docs/tool-routing.md "vidkit embroider" "missing embroider route in tool-routing"

for stem in \
  "track lost on frames" \
  "corner jump" \
  "homography unstable at frame" \
  "green key missing on" \
  "screen mostly not green on frames" \
  "occluder mask is empty at frame 0" \
  "occluder covers" \
  "hand mask is empty at frame 0" \
  "hand mask covers" \
  "shirt lost on frames" \
  "mesh warp failed" \
  "grid points on the shirt" \
  "cannot read fps of" \
  "frame size mismatch" \
  "shirt area too small for design" \
  "--at is not on the shirt" \
  "run tools/setup.sh --ml"; do
  need docs/debugging.md "$stem" "missing docs/debugging.md row for: $stem"
done

if [ "$fail" -eq 0 ]; then echo "PASS surface-insert-contract"; fi
exit "$fail"
