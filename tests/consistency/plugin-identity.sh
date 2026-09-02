#!/usr/bin/env bash
# Plugin identity: the manifest must name and version this plugin as gaspol-video 3.0.0,
# and the repo must carry its own licence plus attribution for the code it adapts.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fail=0

want_name="gaspol-video"
got_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$ROOT/.claude-plugin/plugin.json")"
if [ "$got_name" != "$want_name" ]; then
  echo "FAIL plugin name: got $got_name, want $want_name"
  fail=1
fi

want_version="3.0.0"
got_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT/.claude-plugin/plugin.json")"
if [ "$got_version" != "$want_version" ]; then
  echo "FAIL plugin version: got $got_version, want $want_version"
  fail=1
fi

for f in LICENSE NOTICE; do
  if [ ! -s "$ROOT/$f" ]; then
    echo "FAIL $f: missing or empty"
    fail=1
  fi
done

if [ -s "$ROOT/NOTICE" ]; then
  for upstream in "claude-youtube-editor" "MoneyPrinterTurbo"; do
    if ! grep -q "$upstream" "$ROOT/NOTICE"; then
      echo "FAIL NOTICE: no attribution for $upstream"
      fail=1
    fi
  done
fi

exit $fail
