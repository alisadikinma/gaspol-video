#!/usr/bin/env bash
# GV-8: the skills and the validator must name the tools and fields the GV-8 phases added,
# so a session following the docs reaches qa_frames.py, transition_in, bed_source and pause tags.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() {  # file, fixed string, label
  if ! grep -qF -- "$2" "$1"; then
    echo "FAIL $1 does not $3"
    fail=1
  fi
}

need skills/video-gen/SKILL.md 'qa_frames.py' 'name qa_frames.py'
need skills/video-validate/SKILL.md 'Check V15' 'contain Check V15'
need skills/video-validate/SKILL.md 'Check V16' 'contain Check V16'
need skills/video-post/SKILL.md 'transition_in' 'name transition_in'
need skills/video-post/SKILL.md 'bed_source' 'name bed_source'
need skills/video-script/SKILL.md '[pause:' 'document the [pause: tag'
need agents/video-prompt-reviewer.md 'V16' 'contain V16'
need reference/post-production/13-ffmpeg-edit.md 'transition_in' 'name transition_in'
need reference/post-production/17-music-bed.md 'bed_source' 'name bed_source'
need reference/post-production/10-post-production-pipeline.md 'bed_source' 'name bed_source'
need reference/post-production/10-post-production-pipeline.md 'transition_in' 'name transition_in'
need reference/post-production/10-post-production-pipeline.md 'qa-scene-NN.jpg' 'list .tmp/qa-scene-NN.jpg'
need reference/post-production/10-post-production-pipeline.md 'visual-qa.md' 'list work/visual-qa.md'
need reference/post-production/10-post-production-pipeline.md '4A | 4B | 5 | 6' 'document phase 6 in the renders.json schema'
need reference/post-production/11-voice-cast-and-vo.md '[pause:' 'document the [pause: tag'
need reference/image-video-gen/10-physical-plausibility-gate.md 'qa_frames.py' 'name qa_frames.py'
need skills/video-image/SKILL.md 'asset_library.py' 'name asset_library.py'
need reference/image-video-gen/01-nb2-image-generation.md 'asset_library.py' 'name asset_library.py'

# Phase L: real-run evidence. Each eval records either measured output or an explicit NOT RUN.
for ev in gen-music-video-run pause-tags-run qa-frames-run; do
  f="docs/evals/$ev.md"
  if [ ! -f "$f" ]; then
    echo "FAIL $f missing"
    fail=1
  elif ! grep -qF '## Result' "$f"; then
    echo "FAIL $f has no ## Result section"
    fail=1
  fi
done

exit $fail
