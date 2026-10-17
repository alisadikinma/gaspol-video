#!/usr/bin/env bash
# GV-23 Phase K: video-repackage has a Foreshadow beat (3-6 s) and a two-link merge mode with an
# owner approval stop, a 60 s budget and both links recorded.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
F=skills/video-repackage/SKILL.md
fail=0
need() { if ! grep -qiF -- "$1" "$F"; then echo "FAIL $F lacks: $2"; fail=1; fi; }

need "Foreshadow" "Foreshadow beat"
need "3 to 6 s" "Foreshadow window 3 to 6 s"
need "F13_Short_Form_Timeline.md" "loads F13"
need "60 s" "60 s budget"
need "ref/sumber-1" "first source folder"
need "ref/sumber-2" "second source folder"
need "Merge" "merge step"
need "same" "point table status same"
need "unique" "point table status unique"
need "conflict" "point table status conflict"
need "strongest hook" "strongest hook choice"
need "HARD STOP" "hard stop before storyline"
need "two-part series" "two-part series option"
need "at most two links" "max two links rule"
need "strategic-brief.md" "both links in strategic-brief.md"
need "gen_subs" "transcription via gen_subs"
need "gabung dua video" "trigger gabung dua video"
need "dua link" "trigger dua link"
need "gabungkan link" "trigger gabungkan link"

[ "$fail" -eq 0 ] && echo "PASS repackage-merge" || exit 1
