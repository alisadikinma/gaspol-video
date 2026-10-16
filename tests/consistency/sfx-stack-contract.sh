#!/usr/bin/env bash
# GV-18: layered SFX cues and beat snap. The SFX doc and the post skill must document the stack
# field, the eight new recipes, sfx_snap.py, the density rule, and the order of the SFX pass.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
DOC=reference/post-production/14-sfx-design.md
SKILL=skills/video-post/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

need "$DOC" '"stack"' "stack not documented in $DOC"
for id in sub-boom hit-heavy tail-air whoosh-fast riser-long glitch-hit stinger-up stinger-warn; do
  need "$DOC" "$id" "recipe $id not documented in $DOC"
done
need "$DOC" "sfx_snap.py" "sfx_snap.py not documented in $DOC"
if ! grep -qiE "stack counts as one cue" "$DOC"; then
  echo "FAIL $DOC does not state a stack counts as one cue for density"
  fail=1
fi
need "$SKILL" "sfx_snap.py" "sfx_snap.py not named in $SKILL"
a=$(grep -n -- "--print" "$SKILL" | head -1 | cut -d: -f1)
b=$(grep -n "sfx_snap.py" "$SKILL" | head -1 | cut -d: -f1)
c=$(grep -n "mix_sfx.py {output_folder} --plan" "$SKILL" | head -1 | cut -d: -f1)
if [ -z "$a" ] || [ -z "$b" ] || [ -z "$c" ] || [ "$a" -ge "$b" ] || [ "$b" -ge "$c" ]; then
  echo "FAIL $SKILL must order cue sheet audit, then sfx_snap.py, then mix_sfx.py --plan"
  fail=1
fi
exit $fail
