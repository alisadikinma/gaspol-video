#!/usr/bin/env bash
# v3.11.0 (GV-17): the kinetic text overlay replaces the v3.10.0 gold-serif keyword cards. The
# pattern is documented, wired into video-gen and video-post, and the old tool is kept but marked
# superseded until the new style ships in one real video.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
doc=reference/post-production/19-keyword-text-overlay.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }
need skills/video-gen/SKILL.md "25. **(v3.11.0) Kinetic text overlay.**" "video-gen Rule 25 missing"
need skills/video-gen/SKILL.md "tools/overlay_plan.py" "video-gen Rule 25 does not point at overlay_plan.py"
need skills/video-post/SKILL.md "KineticOverlay" "video-post K.4 does not point at KineticOverlay"
need skills/video-post/SKILL.md "tools/person_mask.py" "video-post K.4 does not point at person_mask.py"
need "$doc" "KineticOverlay" "overlay doc does not name KineticOverlay"
need "$doc" "No box, no pill" "overlay doc lost the no-box rule"
need "$doc" "alphamerge" "overlay doc lost the background-only flash rule"
need "$doc" "key_words" "overlay doc does not explain key_words"
need "$doc" "not subtitles" "overlay doc does not say keywords are not subtitles"
need "$doc" "50%" "overlay doc does not state the text-share limit"
need skills/video-gen/SKILL.md "only the important keywords" "video-gen Rule 25 does not limit text to important keywords"
for fx in "Blur-to-sharp" "Glitch slices" "Count-up" "Handwrite" "Stroke draw" "Exit"; do
  need "$doc" "$fx" "overlay doc does not describe effect: $fx"
done
if grep -qiF "gold serif" "$doc"; then echo "FAIL overlay doc still prescribes the gold serif look"; fail=1; fi
[ ! -e tools/keyword_cards.py ] || { echo "FAIL tools/keyword_cards.py should be removed"; fail=1; }
exit $fail
