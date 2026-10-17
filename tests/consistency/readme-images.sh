#!/usr/bin/env bash
# GV-25: the README shows the whole plugin. Every image it links must exist, and the
# machine-learning stack must be named, so the page cannot drift back to a prompt writer.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
fail=0

for img in $(grep -oE 'docs/img/[A-Za-z0-9_-]+\.(svg|jpg|png)' README.md | sort -u); do
  if [ ! -f "$img" ]; then
    echo "FAIL README.md: links $img, which does not exist"
    fail=1
  fi
done

if ! grep -qE '^## .*Machine learning' README.md; then
  echo "FAIL README.md: no Machine learning section"
  fail=1
fi

for term in "TAPNext" "SAM 2.1" "MediaPipe" "YuNet" "AssemblyAI" "retention_gate" "screen-insert" "embroider"; do
  if ! grep -qF "$term" README.md; then
    echo "FAIL README.md: does not mention $term"
    fail=1
  fi
done

[ "$fail" -eq 0 ] && echo "PASS readme-images"
exit "$fail"
