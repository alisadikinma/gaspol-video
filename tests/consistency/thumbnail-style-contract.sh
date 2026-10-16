#!/usr/bin/env bash
# GV-18 Phase K: the thumbnail style-element menu exists, is slot-based, carries a failure
# table and the honesty guardrail; the skill links it and gates "final" on thumb_verify.py;
# NOTICE credits the source idea.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
DOC=reference/post-production/20-thumbnail-style-elements.md
SKILL=skills/video-package/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

if [ ! -f "$DOC" ]; then
  echo "FAIL doc missing ($DOC)"
  fail=1
else
  # fenced prompt blocks that contain at least one <slot>
  blocks="$(python3 - "$DOC" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
fences = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
print(sum(1 for f in fences if re.search(r"<[A-Za-z][A-Za-z0-9 _-]*>", f)))
PY
)"
  if [ "${blocks:-0}" -lt 4 ]; then echo "FAIL doc has $blocks slot prompt blocks, need at least 4"; fail=1; fi
  if ! grep -qiE '^\|[^|]*symptom[^|]*\|[^|]*fix' "$DOC"; then echo "FAIL doc has no symptom -> fix failure table"; fail=1; fi
  if ! grep -qi 'garbl' "$DOC"; then echo "FAIL failure table does not cover garbled text"; fail=1; fi
  if ! grep -qi 'honesty guardrail' "$DOC"; then echo "FAIL doc does not mention the honesty guardrail"; fail=1; fi
  need "$DOC" "ai-image-carousel-prompt-gen" "doc does not name the render hand-off"
fi

need "$SKILL" "20-thumbnail-style-elements.md" "skill does not link the style doc"
need "$SKILL" "thumb_verify.py init" "skill does not run thumb_verify.py init"
need "$SKILL" "thumb_verify.py check" "skill does not require thumb_verify.py check"
need "$SKILL" "exit 0" "skill does not say check must exit 0 before a thumbnail is final"
need NOTICE "slot-based thumbnail prompt" "NOTICE has no entry for the thumbnail style-element source"
[ -f tools/thumb_verify.py ] || { echo "FAIL tools/thumb_verify.py missing"; fail=1; }
exit $fail
