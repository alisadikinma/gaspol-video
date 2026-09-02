#!/usr/bin/env bash
# The old plugin name must not survive anywhere a user or a tool would read it.
# docs/plans/ is exempt on purpose: those files are historical records of what the
# plugin was called when they were written, and rewriting history there would be a lie.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
old="ai-video-promo-engine"
hits=0

for path in skills reference agents hooks templates tools media README.md CLAUDE.md .claude-plugin; do
  [ -e "$path" ] || continue
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    echo "FAIL old name: $line"
    hits=$((hits + 1))
  done <<< "$(grep -rn "$old" "$path" 2>/dev/null || true)"
done

if [ "$hits" -gt 0 ]; then
  echo "FAIL: $hits occurrence(s) of $old outside docs/plans/"
  exit 1
fi
exit 0
