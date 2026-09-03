#!/usr/bin/env bash
# The orchestrator must run every phase this plugin ships, in the order the pipeline needs.
# A skill that exists but is never invoked by /video-full is a skill nobody discovers: the
# whole point of the orchestrator is that a user who knows one command gets the full pipeline.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
SKILL=skills/video-full/SKILL.md
HOOK=hooks/session-start.sh

[ -f "$SKILL" ] || { echo "FAIL $SKILL missing"; exit 1; }
[ -f "$HOOK" ]  || { echo "FAIL $HOOK missing"; exit 1; }

need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

for s in /video-brainstorm /video-script /video-image /video-gen /video-explainer /video-post /video-package; do
  need "$SKILL" "$s" "video-full does not invoke $s"
done

# Order. Explainer shots are rendered before the platform clips they sit beside, post-
# production runs on finished clips, packaging is last because it needs the master.
line() { grep -nF -- "$1" "$SKILL" | head -1 | cut -d: -f1; }
prev=0
for s in /video-brainstorm /video-script /video-image /video-explainer /video-gen /video-post /video-package; do
  n=$(line "$s")
  if [ -z "$n" ] || [ "$n" -le "$prev" ]; then
    echo "FAIL $s is out of order in the orchestrator (expected after line $prev, found ${n:-none})"
    fail=1
  else
    prev=$n
  fi
done

# The summary has to list what phases 6-7 actually produce, or the user never finds them.
need "$SKILL" "master-mixed.mp4" "production summary does not list the mixed master"
need "$SKILL" "packaging.md" "production summary does not list the packaging output"

# Every shipped skill is announced at session start.
for s in video-full video-brainstorm video-script video-image video-gen video-explainer video-post video-package video-validate video-add-platform; do
  need "$HOOK" "$s" "session-start.sh does not announce $s"
done

[ "$fail" -eq 0 ] && echo "PASS orchestrator-phases"
exit "$fail"
