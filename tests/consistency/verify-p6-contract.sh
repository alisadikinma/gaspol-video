#!/usr/bin/env bash
# P6 (verify_render.py) must be documented where a reader would look for it: the
# validator's check list and the top-level tool/architecture doc. Spec §8.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() { # need <file> <needle> <message>
  if ! grep -qF -- "$2" "$1"; then
    echo "FAIL $3"
    fail=1
  fi
}

need skills/video-validate/SKILL.md "Check P6"        "Check P6 not defined in skills/video-validate/SKILL.md"
need CLAUDE.md                      "P6"              "P6 not mentioned in CLAUDE.md"
need CLAUDE.md                      "verify_render.py" "verify_render.py not mentioned in CLAUDE.md"

exit $fail
