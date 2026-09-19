#!/usr/bin/env bash
# v3.2.0 docs sync gate. Every tool this ticket ships or ported must be named in
# CLAUDE.md's Architecture table, every post-production reference must be listed
# there too, the plugin version must be bumped, and NOTICE must carry the new
# attribution debt. This is the check `docs(GV-2): sync CLAUDE.md, NOTICE and
# config for 3.2.0` exists to satisfy.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

for f in tools/*.py; do
  base="$(basename "$f")"
  case "$base" in
    __init__.py|_venv.py) continue ;;
  esac
  if ! grep -qF "$base" CLAUDE.md; then
    echo "FAIL $f not listed in CLAUDE.md"
    fail=1
  fi
done

for f in tools/*.mjs; do
  base="$(basename "$f")"
  if ! grep -qF "$base" CLAUDE.md; then
    echo "FAIL $f not listed in CLAUDE.md"
    fail=1
  fi
done

for f in reference/post-production/*.md; do
  base="$(basename "$f")"
  if ! grep -qF "$base" CLAUDE.md; then
    echo "FAIL reference/post-production/$base not listed in CLAUDE.md"
    fail=1
  fi
done

if ! grep -qF '"version": "3.3.0"' .claude-plugin/plugin.json; then
  echo "FAIL plugin.json version is not 3.3.0"
  fail=1
fi

for needle in capture_web screencast verify_cut make_stems gen_music clean_voice composite_logo thumb_scrim yt_stats bake.py; do
  if ! grep -qF "$needle" NOTICE; then
    echo "FAIL NOTICE does not mention $needle"
    fail=1
  fi
done

exit $fail
