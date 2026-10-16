#!/bin/bash
# PreToolUse (Write|Edit): remind which registered tools do similar work.
# Reminds, never blocks: always exit 0; failures print one stderr line.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${CLAUDE_PLUGIN_ROOT:-$HERE}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "tool-reminder: python3 not found" >&2
  exit 0
fi

python3 "$HERE/tools/registry_build.py" --root "$ROOT" hook || echo "tool-reminder: hook failed" >&2
exit 0
