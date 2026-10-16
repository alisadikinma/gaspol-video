#!/usr/bin/env bash
# GV-20 write-time reminder hook, end to end. The hook reminds, never blocks:
# every path below must exit 0, and only a firing payload may print to stdout.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
HOOK="$ROOT/hooks/tool-reminder.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

run() { # run <plugin-root> <stdin>; sets OUT ERR RC
  CLAUDE_PLUGIN_ROOT="$1" "$HOOK" <<<"$2" >"$TMP/out" 2>"$TMP/err"
  RC=$?
  OUT="$(cat "$TMP/out")"
  ERR="$(cat "$TMP/err")"
}

check() { # check <name> <condition-result>
  if [ "$2" != 0 ]; then echo "FAIL tool-reminder: $1"; fail=1; fi
}

FIRE='{"tool_name":"Write","tool_input":{"file_path":"/tmp/x.py","content":"import subprocess; subprocess.run([\"ffmpeg\",\"-f\",\"concat\"])"}}'
MD='{"tool_name":"Write","tool_input":{"file_path":"/tmp/x.md","content":"ffmpeg -f concat"}}'
INTOOLS="{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$ROOT/tools/x.py\",\"content\":\"ffmpeg -f concat\"}}"

run "$ROOT" "$FIRE"
check "firing payload exits 0" "$RC"
[[ "$OUT" == *hookSpecificOutput* && "$OUT" == *additionalContext* ]]
check "firing payload prints hookSpecificOutput and additionalContext" "$?"
python3 -c 'import json,sys;json.loads(sys.stdin.read())' <<<"$OUT"
check "firing payload prints valid JSON" "$?"

run "$ROOT" "$MD"
[ "$RC" = 0 ] && [ -z "$OUT" ]
check ".md payload prints nothing and exits 0" "$?"

run "$ROOT" "$INTOOLS"
[ "$RC" = 0 ] && [ -z "$OUT" ]
check "payload under tools/ prints nothing and exits 0" "$?"

run "$ROOT" "this is not json"
[ "$RC" = 0 ] && [ -z "$OUT" ] && [[ "$ERR" == tool-reminder:* ]]
check "garbage stdin: silent stdout, exit 0, stderr tool-reminder:" "$?"

run "$TMP" "$FIRE"
[ "$RC" = 0 ] && [ -z "$OUT" ] && [[ "$ERR" == tool-reminder:* ]]
check "unreadable registry: silent stdout, exit 0, stderr tool-reminder:" "$?"

exit $fail
