#!/usr/bin/env bash
# GV-18: the music brief route. The bed doc and the post skill must both name the tool and the
# brief file, state the brief shape, and say the tone table is only the fallback.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
DOC=reference/post-production/17-music-bed.md
SKILL=skills/video-post/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

for f in "$DOC" "$SKILL"; do
  need "$f" "music_brief.py" "$f does not mention music_brief.py"
  need "$f" "work/music-brief.json" "$f does not mention work/music-brief.json"
  need "$f" "work/music-palette.json" "$f does not mention work/music-palette.json"
done
need "$DOC" "The brief route" "$DOC has no 'The brief route' section"
for key in topic domain tone sound_world segments from_s to_s beat energy; do
  need "$DOC" "\"$key\"" "$DOC brief shape lacks \"$key\""
done
for beat in hook build body peak resolve cta; do
  need "$DOC" "$beat" "$DOC beat vocabulary lacks $beat"
done
if ! grep -qiE "fallback" "$DOC" || ! grep -qiE "only the fallback|is the fallback|as the fallback" "$DOC"; then
  echo "FAIL $DOC does not say the tone table is the fallback"
  fail=1
fi
need "$SKILL" "gen_music.py --recipes {output_folder}/work/music-palette.json --only" "$SKILL does not pass --recipes and --only to gen_music.py"
need "$SKILL" "--dry-run" "$SKILL does not dry-run before billing"
if ! grep -qiE "confirm" "$SKILL"; then echo "FAIL $SKILL has no user confirmation before billing"; fail=1; fi
a=$(grep -n "music_brief.py" "$SKILL" | head -1 | cut -d: -f1)
b=$(grep -n "mix_music.py" "$SKILL" | head -1 | cut -d: -f1)
if [ -z "$a" ] || [ -z "$b" ] || [ "$a" -ge "$b" ]; then
  echo "FAIL music_brief.py must come before mix_music.py in $SKILL"
  fail=1
fi
exit $fail
