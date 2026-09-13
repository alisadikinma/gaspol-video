#!/usr/bin/env bash
# Screen Source routing must be defined in Phase 3 (scene-plan) and honoured in
# Phase 4A/4B, and the validator must catch a scene that skips the rule (C11).
# It must NOT disturb the pre-existing Render Path / Scene Type columns.
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
need "$BRIDGE" "Screen Source"    "Screen Source column not defined in $BRIDGE"
need "$BRIDGE" "capture"          "Screen Source value capture missing in $BRIDGE"
need "$BRIDGE" "mock"             "Screen Source value mock missing in $BRIDGE"
need "$BRIDGE" "gen_app_screen.py" "gen_app_screen.py not referenced in $BRIDGE"

# pre-existing columns must survive untouched
need "$BRIDGE" "Render Path"  "pre-existing Render Path column disappeared from $BRIDGE"
need "$BRIDGE" "Scene Type"   "pre-existing Scene Type column disappeared from $BRIDGE"

need skills/video-script/SKILL.md  "Screen Source" "video-script Phase 3 does not assign Screen Source"
need skills/video-image/SKILL.md   "Rule 34"       "video-image does not define Rule 34 for Screen Source"
need agents/video-prompt-reviewer.md "C11."        "validator check C11 not defined in the prompt reviewer"
need skills/video-package/SKILL.md "simulated"     "video-package Step 7.5 does not read the simulated flag"

# C11 honesty extension: a mocked/simulated screen must never be presented as shipped/real.
need agents/video-prompt-reviewer.md "simulated"      "C11 in the prompt reviewer does not mention simulated screens"
need skills/video-validate/SKILL.md  "simulated"      "video-validate does not check simulated-screen honesty"

exit $fail
