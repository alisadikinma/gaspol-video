#!/usr/bin/env bash
# Every tool must be runnable the way the skills actually call it.
#
# Each SKILL.md invokes tools as `python3 tools/<name>.py <project>`, which puts tools/ on
# sys.path but NOT the repo root. A tool that does `from tools.x import y` without first
# inserting the repo root into sys.path imports fine from a unit test (run from the repo
# root) and dies on its first real invocation:
#
#   ModuleNotFoundError: No module named 'tools'
#
# That is how gen_captions.py, plan_motion.py and make_stems.py all shipped broken. The
# idiom that fixes it is already in five other tools:
#
#   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
#
# `--help` is the cheapest invocation that exercises every module-level import without
# touching the network, ffmpeg or a project directory.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

for f in tools/*.py; do
  base="$(basename "$f")"
  case "$base" in
    __init__.py|_venv.py) continue ;;
  esac
  if ! python3 "$f" --help >/dev/null 2>&1; then
    echo "FAIL $f cannot be run as a script — $(python3 "$f" --help 2>&1 | tail -1)"
    fail=1
  fi
done

exit $fail
