#!/usr/bin/env bash
# Render Path routing must be defined in Phase 3 and honoured in Phase 4B.
# It must NOT collide with the pre-existing Scene Type column, which means
# something else entirely (B-Roll vs Presenter) and has to survive untouched.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() { # need <file> <needle> <message>
  if ! grep -qF "$2" "$1"; then
    echo "FAIL $3"
    fail=1
  fi
}

BRIDGE=reference/script-to-scene-bridge.md
need "$BRIDGE" "Render Path"  "Render Path column not defined in $BRIDGE"
need "$BRIDGE" "live-action"  "Render Path value live-action missing in $BRIDGE"
need "$BRIDGE" "explainer"    "Render Path value explainer missing in $BRIDGE"

# the old column must still be there, with its own meaning intact
need "$BRIDGE" "Scene Type"   "pre-existing Scene Type column disappeared from $BRIDGE"
need "$BRIDGE" "Presenter"    "pre-existing Scene Type value Presenter disappeared from $BRIDGE"
need "$BRIDGE" "B-Roll"       "pre-existing Scene Type value B-Roll disappeared from $BRIDGE"

need skills/video-script/SKILL.md "Render Path" "video-script Phase 3 does not assign Render Path"
need skills/video-image/SKILL.md  "explainer"   "video-image does not mention explainer scenes at all"
need agents/video-prompt-reviewer.md "C6." "validator check C6 not defined in the prompt reviewer"

# Phase 4B must skip explainer scenes, stated in words a reader can find
if ! grep -qiE "explainer.*(skip|no keyframe)|skip.*explainer" skills/video-image/SKILL.md; then
  echo "FAIL video-image does not state that explainer scenes are skipped in Phase 4B"
  fail=1
fi

exit $fail
