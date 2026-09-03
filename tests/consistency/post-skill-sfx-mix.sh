#!/usr/bin/env bash
# /video-post passes 3-5: SFX, subtitles + music, final mix. The audit gate before mixing
# and the audibility thresholds are the two things a reader must not have to guess at.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
SKILL=skills/video-post/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

need "$SKILL" "Pass 3" "pass 3 (SFX) not documented in $SKILL"
need "$SKILL" "Pass 4" "pass 4 (subtitles + music) not documented in $SKILL"
need "$SKILL" "Pass 5" "pass 5 (final mix) not documented in $SKILL"
for tool in gen_sfx.py mix_sfx.py gen_subs.py burn_subs.py mix_music.py; do
  need "$SKILL" "$tool" "passes 3-5 do not name $tool"
done
need "$SKILL" "+4 dB"  "the story-critical audibility threshold is not stated"
need "$SKILL" "0.3s"   "the transient measurement window is not stated"
need "$SKILL" "-14 LUFS" "the loudness target is not stated"

# the audit gate must be described as hard, and must come before mixing
if ! grep -qiE "hard.*(gate|audit)|audit.*hard" "$SKILL"; then
  echo "FAIL the cue-sheet audit gate is not described as hard"
  fail=1
fi
a=$(grep -n "Pass 3" "$SKILL" | head -1 | cut -d: -f1)
b=$(grep -n "Pass 5" "$SKILL" | head -1 | cut -d: -f1)
if [ -z "$a" ] || [ -z "$b" ] || [ "$a" -ge "$b" ]; then
  echo "FAIL pass 3 must be documented before pass 5"
  fail=1
fi
exit $fail
