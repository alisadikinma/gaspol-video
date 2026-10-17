#!/usr/bin/env bash
# GV-24 Phase L: the real-clip proof exists. Every clip section names its source, command,
# returned JSON and owner verdict; a skipped clip kind must say who decided and why.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
f="docs/evals/surface-insert-run.md"
[ -f "$f" ] || { echo "FAIL surface-insert-run.md missing"; exit 1; }
fail=0
for key in shirt_source shirt_command shirt_result shirt_qa shirt_verdict; do
  if ! grep -Eq "^${key}:[[:space:]]*[^[:space:]]+" "$f"; then
    echo "FAIL surface-insert-run.md key '${key}:' missing or empty"
    fail=1
  fi
done
if grep -Eq "^screen_skipped:[[:space:]]*[^[:space:]]+" "$f"; then
  :
else
  for key in screen_source screen_command screen_result screen_verdict; do
    if ! grep -Eq "^${key}:[[:space:]]*[^[:space:]]+" "$f"; then
      echo "FAIL surface-insert-run.md key '${key}:' missing (or add screen_skipped: <who, why>)"
      fail=1
    fi
  done
fi
qa="$(grep -E "^shirt_qa:" "$f" | sed -E 's/^shirt_qa:[[:space:]]*//; s/[[:space:]].*$//' || true)"
if [ -n "$qa" ] && [ ! -f "$qa" ]; then echo "FAIL shirt_qa file $qa not in the repo"; fail=1; fi
[ "$fail" -eq 0 ] || exit 1
echo "PASS surface-insert-run.md has the real-clip proof"
