#!/usr/bin/env bash
# CLAUDE.md's Reference Files tables and the reference/ folder must agree in BOTH
# directions: no reference file is undocumented, and no documented file is missing.
# Cross-file drift here is the failure /video-validate --refs exists to catch, and it
# is cheap enough to catch on every run instead.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

# required: references this ticket adds. The list grows one phase at a time, so each
# phase starts red on its own file rather than on a list somebody has to remember to fill.
REQUIRED="post-production/10-post-production-pipeline.md post-production/11-voice-cast-and-vo.md post-production/13-ffmpeg-edit.md post-production/14-sfx-design.md post-production/16-subtitles-and-captions.md post-production/17-music-bed.md"

for rel in $REQUIRED; do
  if [ ! -f "reference/$rel" ]; then
    echo "FAIL: reference/$rel does not exist"
    fail=1
  elif ! grep -qF "$rel" CLAUDE.md; then
    echo "FAIL: reference/$rel not listed in CLAUDE.md"
    fail=1
  fi
done

# forward: every reference/**/*.md is named somewhere in CLAUDE.md
while IFS= read -r f; do
  rel="${f#reference/}"
  if ! grep -qF "$rel" CLAUDE.md; then
    echo "FAIL undocumented: reference/$rel is not listed in CLAUDE.md"
    fail=1
  fi
done <<< "$(find reference -name '*.md' -type f | sed 's|^\./||' | sort)"

# reverse: every reference file named in CLAUDE.md's tables exists on disk
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  if [ ! -f "reference/$rel" ]; then
    echo "FAIL missing: CLAUDE.md names reference/$rel, which does not exist"
    fail=1
  fi
done <<< "$(grep -oE '\`[A-Za-z0-9_./-]+\.md\`' CLAUDE.md \
            | tr -d '`' \
            | grep -E '^(global-promo-config|creator-profile-system|script-to-scene-bridge|storytelling_script_gen/|image-video-gen/|post-production/)' \
            | sort -u)"

exit $fail
