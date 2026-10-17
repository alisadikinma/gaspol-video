#!/usr/bin/env bash
# GV-23 Phase L: video-package keeps three separate short-form texts; doc 21 has a 9:16 path
# (cover rendered without text, title stamped by vidkit title, gated by layout_gate.py).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
DOC=reference/post-production/21-thumbnail-style-elements.md
SKILL=skills/video-package/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

need "$SKILL" "Thumbnail title" "skill lacks the thumbnail title output"
need "$SKILL" "3-5 words" "skill lacks thumbnail title length 3-5 words"
need "$SKILL" "Video title" "skill lacks the short-form video title output"
need "$SKILL" "5-9 words" "skill lacks video title length 5-9 words"
need "$SKILL" "ALL CAPS" "skill does not require ALL CAPS titles"
need "$SKILL" "Hook on-screen text" "skill lacks the hook on-screen text output"
need "$SKILL" "4-7 words" "skill lacks hook text length 4-7 words"
need "$SKILL" "extreme number" "skill lacks the title formula"
need "$SKILL" "numbers must come from the brief" "skill lacks the no-invented-numbers guardrail"
need "$SKILL" "vidkit title" "skill does not stamp the title with vidkit title"

need "$DOC" "## 8. 9:16 path" "doc 21 has no 9:16 path section"
need "$DOC" "no text, no letters, no captions" "doc 21 lacks the no-text negative for the cover"
need "$DOC" "python3 -m tools.vidkit title" "doc 21 lacks the vidkit title command"
need "$DOC" "media/layout-profiles.json" "doc 21 does not source title numbers from the profile"
need "$DOC" "tafsiran" "doc 21 does not say the title numbers are tafsiran"
need "$DOC" "never over the face" "doc 21 lacks never over the face"
need "$DOC" "layout_gate.py check" "doc 21 lacks the layout gate before final"
need "$DOC" "extreme number" "doc 21 lacks the title formula"
need "$DOC" "SISKA KOHL BELI NASI GORENG SEHARGA 400 JUTA!" "doc 21 lacks the formula example"
exit $fail
