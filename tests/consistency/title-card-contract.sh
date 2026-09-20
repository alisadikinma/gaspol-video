#!/usr/bin/env bash
# Title Card must be defined in Phase 3 (scene-plan) and its caption-hold rule stated
# where Pass 4.1 lives. It must NOT disturb the pre-existing Render Path / Screen
# Source columns.
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

BRIDGE=reference/script-to-scene-bridge.md
need "$BRIDGE" "Title Card"  "Title Card column not defined in $BRIDGE"
need "$BRIDGE" "left:"       "Title Card value 'left:' missing in $BRIDGE"
need "$BRIDGE" "right:"      "Title Card value 'right:' missing in $BRIDGE"

# pre-existing columns must survive untouched
need "$BRIDGE" "Render Path"    "pre-existing Render Path column disappeared from $BRIDGE"
need "$BRIDGE" "live-action"    "pre-existing Render Path value live-action disappeared from $BRIDGE"
need "$BRIDGE" "explainer"      "pre-existing Render Path value explainer disappeared from $BRIDGE"
need "$BRIDGE" "Screen Source"  "pre-existing Screen Source column disappeared from $BRIDGE"
need "$BRIDGE" "capture"        "pre-existing Screen Source value capture disappeared from $BRIDGE"
need "$BRIDGE" "mock"           "pre-existing Screen Source value mock disappeared from $BRIDGE"

need skills/video-script/SKILL.md "Title Card"     "video-script Phase 3 does not assign Title Card"
need skills/video-script/SKILL.md "Render Path"    "video-script Phase 3 lost its Render Path assignment"
need skills/video-script/SKILL.md "Screen Source"  "video-script Phase 3 lost its Screen Source assignment"

# The caption-hold rule must be stated where Pass 4.1 lives, so a gap in the captions
# is explainable without reading tools/gen_captions.py.
need skills/video-post/SKILL.md "captions_held_until_s" "video-post does not state the caption-hold rule (captions_held_until_s)"
need skills/video-post/SKILL.md "2.5"                   "video-post does not state the 2.5s title-card hold duration"

exit $fail
