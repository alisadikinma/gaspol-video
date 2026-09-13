#!/usr/bin/env bash
# Screencast shots (Phase 4.5, scenes whose Screen Source is capture|mock) need a
# reference document and a skill step that actually points at it and at qa-frames.mjs.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() { # need <file> <needle> <message>
  if [ ! -f "$1" ]; then
    echo "FAIL $1 missing"
    fail=1
    return
  fi
  if ! grep -qF -- "$2" "$1"; then
    echo "FAIL $3"
    fail=1
  fi
}

REF=reference/post-production/18-screencast.md
need "$REF" "ScreencastPage"    "18-screencast.md does not document ScreencastPage"
need "$REF" "qa-frames.mjs"     "18-screencast.md does not reference qa-frames.mjs"
need "$REF" "vo-manifest.json"  "18-screencast.md does not reference vo-manifest.json"
need "$REF" "simulated"         "18-screencast.md does not mention the simulated flag / honesty rule"

EXPLAINER_REF=reference/post-production/12-remotion-explainer.md
need "$EXPLAINER_REF" "## Style presets" "12-remotion-explainer.md has no ## Style presets section"

need skills/video-explainer/SKILL.md "18-screencast" "video-explainer does not reference 18-screencast.md"
need skills/video-explainer/SKILL.md "qa-frames.mjs" "video-explainer Step 4.5.3 does not use qa-frames.mjs"

need CLAUDE.md "18-screencast.md" "CLAUDE.md does not list reference/post-production/18-screencast.md"

exit $fail
