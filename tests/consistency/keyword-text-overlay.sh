#!/usr/bin/env bash
# v3.10.0: keyword text overlay pattern is documented, wired into video-gen and shipped as a tool.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }
need skills/video-gen/SKILL.md "25. **(v3.10.0) Keyword text overlay pattern.**" "video-gen Rule 25 missing"
need skills/video-post/SKILL.md "tools/keyword_cards.py" "video-post K.4 does not point at keyword_cards.py"
need reference/post-production/19-keyword-text-overlay.md "No box, no pill" "overlay doc lost the no-box rule"
need reference/post-production/19-keyword-text-overlay.md "alphamerge" "overlay doc lost the background-only flash rule"
[ -f tools/keyword_cards.py ] || { echo "FAIL tools/keyword_cards.py missing"; fail=1; }
python3 -c "import ast,sys; ast.parse(open('tools/keyword_cards.py').read())" || fail=1
exit $fail
