#!/usr/bin/env bash
# GV-23 Phase J: video type decides the format; 9:16 scripts follow the F13 timeline.
# Greps skill text only; the F13 file and the timeline command ship in other phases.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
B="skills/video-brainstorm/SKILL.md"
S="skills/video-script/SKILL.md"
C="reference/global-promo-config.md"

need() { grep -qF -- "$2" "$1" || { echo "FAIL: $1 lacks '$2'"; fail=1; }; }

for t in presentasi promo isu edukasi; do need "$B" "\`$t\`"; done
need "$B" "Step 1.0b"
need "$B" "/video-repackage"
need "$B" "Format Confirmation"
need "$B" "video_type"
need "$B" "max_duration_s"
need "$B" "platforms:"
need "$B" "aspect:"
need "$B" "legacy \`issue\`"
need "$B" "## Platform:"
if grep -qF "Platform Selection" "$B"; then echo "FAIL: $B still has 'Platform Selection'"; fail=1; fi
if grep -qF '"Platform utama untuk video ini?"' "$B"; then echo "FAIL: $B still asks the platform question"; fail=1; fi

need "$S" "F13_Short_Form_Timeline.md"
need "$S" "aspect: 9:16"
need "$S" "Tahap"
need "$S" "Detik"
need "$S" "viral_checklist.py timeline"
need "$S" "28. **(GV-23)"

need "$C" "presentasi"
need "$C" "edukasi"

[ "$fail" -eq 0 ] && echo "PASS video-type-routing"
exit "$fail"
