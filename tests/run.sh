#!/usr/bin/env bash
# Dependency-free test runner for gaspol-video.
#
# Three groups, run in order. Every group is optional in the sense that an EMPTY
# group passes; a group with failing members fails the run. There is no pytest and
# no npm here on purpose: bash, python3 -m unittest (stdlib) and node --test (built
# in) are all present on any machine that can run this plugin's tools at all.
#
#   bash tests/run.sh            run everything
#   bash tests/run.sh consistency|py|node   run one group
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
only="${1:-all}"
rc=0

# NOTE: bash 3.2 (the macOS default) has no mapfile and no readarray. Everything
# here stays POSIX-ish on purpose so the suite runs on a stock Mac.
run_consistency() {
  pass=0
  fail=0
  found=0
  for f in tests/consistency/*.sh; do
    [ -f "$f" ] || continue
    found=1
    if bash "$f"; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      echo "             ^ failed: $f"
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "consistency  SKIP  no checks yet"
    return 0
  fi
  if [ "$fail" -eq 0 ]; then
    echo "consistency  PASS  $pass checks"
    return 0
  fi
  echo "consistency  FAIL  $fail of $((pass + fail)) checks"
  return 1
}

run_py() {
  if [ -z "$(find tests/py -maxdepth 1 -name 'test_*.py' -type f 2>/dev/null)" ]; then
    echo "python       SKIP  no tests yet"
    return 0
  fi
  if python3 -m unittest discover -s tests/py -t . -q; then
    echo "python       PASS"
    return 0
  fi
  echo "python       FAIL"
  return 1
}

run_node() {
  if [ -z "$(find tests/node -maxdepth 1 -name '*.test.mjs' -type f 2>/dev/null)" ]; then
    echo "node         SKIP  no tests yet"
    return 0
  fi
  # Node needs a glob here, not a bare directory.
  if node --test "tests/node/*.test.mjs"; then
    echo "node         PASS"
    return 0
  fi
  echo "node         FAIL"
  return 1
}

case "$only" in
  consistency) run_consistency || rc=1 ;;
  py)          run_py          || rc=1 ;;
  node)        run_node        || rc=1 ;;
  all)
    run_consistency || rc=1
    run_py          || rc=1
    run_node        || rc=1
    ;;
  *) echo "usage: bash tests/run.sh [all|consistency|py|node]"; exit 2 ;;
esac

[ "$rc" -eq 0 ] && echo "RESULT       PASS" || echo "RESULT       FAIL"
exit $rc
