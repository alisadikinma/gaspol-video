#!/usr/bin/env bash
# GV-25: CLAUDE.md is loaded into every session in this repo, so every line costs tokens on
# every turn. History lives in CHANGELOG.md and the error table in docs/debugging.md.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
fail=0
max=400

lines=$(wc -l < CLAUDE.md | tr -d ' ')
if [ "$lines" -gt "$max" ]; then
  echo "FAIL CLAUDE.md: $lines lines (max $max)"
  fail=1
fi
if grep -qE '^### v[0-9]' CLAUDE.md; then
  echo "FAIL CLAUDE.md: carries changelog sections; they belong in CHANGELOG.md"
  fail=1
fi

[ "$fail" -eq 0 ] && echo "PASS claude-md-size"
exit "$fail"
