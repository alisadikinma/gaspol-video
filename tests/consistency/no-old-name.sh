#!/usr/bin/env bash
# The old plugin name must not survive anywhere a user or a tool would read it.
# -I skips binary files: a .pyc caches the absolute build path, which contains the old
# folder name and says nothing about the source.
# docs/plans/ is exempt on purpose: those files are historical records of what the
# plugin was called when they were written, and rewriting history there would be a lie.
# A line that RECORDS the rename is exempt for the same reason — someone arriving from
# the old name has to be able to learn it moved. The exemption is narrow on purpose: the
# line must literally say "Renamed" or "renamed from". Anything else is a stale reference.
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
  done <<< "$(grep -rnI "$old" "$path" 2>/dev/null | grep -vE 'Renamed|renamed from' || true)"
done

if [ "$hits" -gt 0 ]; then
  echo "FAIL: $hits occurrence(s) of $old outside docs/plans/"
  exit 1
fi
exit 0
