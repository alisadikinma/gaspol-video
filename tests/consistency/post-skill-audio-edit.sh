#!/usr/bin/env bash
# /video-post pass 1 (audio) and pass 2 (edit): documented, in order, naming their tools,
# and carrying the degradation policy. A skill that calls a tool it never names cannot be
# followed by anyone reading only the skill.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
SKILL=skills/video-post/SKILL.md

[ -f "$SKILL" ] || { echo "FAIL $SKILL missing"; exit 1; }

need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

need "$SKILL" "Pass 1"  "pass 1 (audio) not documented"
need "$SKILL" "Pass 2"  "pass 2 (edit) not documented"
for tool in gen_vo.mjs voice_changer.mjs probe_clips.py edit_render.py; do
  need "$SKILL" "$tool" "pass 1-2 does not name $tool"
done
need "$SKILL" "audio-plan.json" "audio-plan.json contract not referenced"
need "$SKILL" "edit-plan.json"  "edit-plan.json contract not referenced"
need "$SKILL" "Degradation"     "degradation policy missing"

# order: audio before edit, because the VO sets how long a beat really is
a=$(grep -n "Pass 1" "$SKILL" | head -1 | cut -d: -f1)
b=$(grep -n "Pass 2" "$SKILL" | head -1 | cut -d: -f1)
if [ -z "$a" ] || [ -z "$b" ] || [ "$a" -ge "$b" ]; then
  echo "FAIL pass 1 must be documented before pass 2"
  fail=1
fi
exit $fail

# A clip with two speakers must not be converted whole — that rewrites the wrong voices.
need skills/video-post/SKILL.md "--spans"
need skills/video-post/SKILL.md "MANDATORY whenever the scene has more than one speaker"
need reference/post-production/11-voice-cast-and-vo.md "--spans"
