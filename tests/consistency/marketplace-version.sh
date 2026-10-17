#!/usr/bin/env bash
# Release gate: plugin.json version equals the gaspol-video entry in the gaspol-one
# marketplace (marketplace.json and its README table). The marketplace lives in a
# sibling repo; this runs from the main checkout or any worktree, so the repo root is
# resolved through git's common dir. GASPOL_ONE_DIR overrides. Absent -> skip with a note.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
common="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
main_root="$(dirname "$common")"
one="${GASPOL_ONE_DIR:-$(dirname "$main_root")/gaspol-one}"
mp="$one/.claude-plugin/marketplace.json"
if [ ! -f "$mp" ]; then
  echo "SKIP marketplace-version: $mp not found"
  exit 0
fi
want="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT/.claude-plugin/plugin.json")"
got="$(python3 -c '
import json,sys
for p in json.load(open(sys.argv[1]))["plugins"]:
    if p["name"]=="gaspol-video": print(p["version"])
' "$mp")"
fail=0
if [ "$got" != "$want" ]; then
  echo "FAIL marketplace.json gaspol-video version: got $got, want $want"
  fail=1
fi
if [ -f "$one/README.md" ] && ! grep -E '^\| \[gaspol-video\]' "$one/README.md" | grep -qF "| $want |"; then
  echo "FAIL gaspol-one README version table: gaspol-video row lacks $want"
  fail=1
fi
exit $fail
