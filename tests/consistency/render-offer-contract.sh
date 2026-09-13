#!/usr/bin/env bash
# Phase 4/5 render offers must be wired into the skills and the global config,
# so a Claude session actually calls the indusia MCP tools instead of only
# printing copy-paste prompts.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

need() { # need <file> <needle> <message>
  if ! grep -qF -- "$2" "$1"; then
    echo "FAIL $3"
    fail=1
  fi
}

IMAGE_SKILL=skills/video-image/SKILL.md
need "$IMAGE_SKILL" "mcp__indusia-image-gen__generate_image" "video-image has no RENDER OFFER step"
need "$IMAGE_SKILL" "nano-banana-2"                           "video-image RENDER OFFER missing nano-banana-2 model"
need "$IMAGE_SKILL" "renders.json"                            "video-image RENDER OFFER does not reference the render ledger"
need "$IMAGE_SKILL" "RENDER OFFER"                             "video-image has no RENDER OFFER step heading"

CONFIG=reference/global-promo-config.md
need "$CONFIG" "29.6"          "global-promo-config missing section 29.6 Rendering"
need "$CONFIG" "render_offer"  "global-promo-config §29.6 missing render_offer key"

GEN_SKILL=skills/video-gen/SKILL.md
need "$GEN_SKILL" "mcp__indusia-video-gen__generate_video" "video-gen has no RENDER OFFER step"
need "$GEN_SKILL" "veo-3.1-fast"                            "video-gen RENDER OFFER missing veo-3.1-fast model"
need "$GEN_SKILL" "RENDER OFFER"                            "video-gen has no RENDER OFFER step heading"
need "$GEN_SKILL" "security camera"                         "video-gen RENDER OFFER missing the security camera vault trap check"
need "$GEN_SKILL" "probe_clips.py"                          "video-gen RENDER OFFER does not run probe_clips.py after the batch"

exit $fail
