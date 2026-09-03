#!/usr/bin/env bash
# Packaging decides WHAT to bet on; rendering the image belongs to the image plugin.
# The routing must stay SOFT: a hard dependency would let a third-party entry disable
# every unrelated skill in this plugin.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
SKILL=skills/video-package/SKILL.md
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

[ -f "$SKILL" ] || { echo "FAIL $SKILL missing"; exit 1; }

need "$SKILL" "ai-image-carousel-prompt-gen" "the image plugin is not named as the render route"
need "$SKILL" "soft" "the reference to the image plugin is not described as soft"
need "$SKILL" "uncalibrated" "cold-start CTR rules are not labelled uncalibrated"

# no image generation may happen inside this plugin
for needle in "nano-banana" "generate_image" "gemini" "imagen"; do
  if grep -qiF -- "$needle" "$SKILL"; then
    echo "FAIL $SKILL appears to call an image generator itself ($needle)"
    fail=1
  fi
done

# and no hard dependency in the manifest
if python3 -c "import json,sys; sys.exit(0 if 'dependencies' in json.load(open('.claude-plugin/plugin.json')) else 1)"; then
  echo "FAIL plugin.json declares dependencies — routing must stay soft"
  fail=1
fi
exit $fail
