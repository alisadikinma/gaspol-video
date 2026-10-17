#!/usr/bin/env bash
# GV-25: one route for a panel on a phone/monitor screen. Skills place it with
# `vidkit screen-insert`; the old Remotion QuadScreenTracked + track_screen.py pipeline
# (whose failures caused GV-24) stays only as legacy, and `vidkit smooth-track` is gone.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
fail=0

for f in skills/*/SKILL.md agents/*.md; do
  [ -f "$f" ] || continue
  if grep -q "QuadScreenTracked" "$f"; then
    echo "FAIL $f: routes to QuadScreenTracked"
    fail=1
  fi
  if grep -q "smooth-track" "$f"; then
    echo "FAIL $f: mentions the retired vidkit smooth-track"
    fail=1
  fi
done

for f in skills/video-explainer/SKILL.md skills/video-image/SKILL.md; do
  if ! grep -q "screen-insert" "$f"; then
    echo "FAIL $f: does not route screen panels to vidkit screen-insert"
    fail=1
  fi
done

if ! head -5 templates/remotion/lib/quad-screen.tsx | grep -q "LEGACY"; then
  echo "FAIL templates/remotion/lib/quad-screen.tsx: header does not say LEGACY"
  fail=1
fi

if ! head -15 tools/track_screen.py | grep -q -- "--corners"; then
  echo "FAIL tools/track_screen.py: docstring does not say it only reads --corners"
  fail=1
fi

[ "$fail" -eq 0 ] && echo "PASS screen-route-contract"
exit "$fail"
