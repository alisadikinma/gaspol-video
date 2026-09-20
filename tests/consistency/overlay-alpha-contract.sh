#!/usr/bin/env bash
# A template whose documented placement is `composite.py overlay` MUST declare
# transparent: true in its compositionConfig.
#
# tools/composite.py overlay calls require_alpha(), which probes the real pix_fmt and
# refuses a shot without an alpha channel. templates/remotion/scripts/gen-registry.mjs
# only writes transparent into shots.manifest.json when it finds `transparent: true` in
# the source's compositionConfig block. A template that omits it therefore renders an
# opaque file and, per reference/post-production/12-remotion-explainer.md line 105,
# "blacks out the picture it was meant to decorate".
#
# Captions.template.tsx and TitleCard.template.tsx both shipped without it (GV-7 phases
# C and D); their own header comments document composite.py overlay as the placement.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

for f in templates/remotion/*.tsx; do
  # Only templates that document themselves as overlays are held to this.
  # "composite.py overlay", "composite it over the master", "as an overlay" — any of the
  # ways a template states that it is placed on top of the picture rather than replacing it.
  if grep -qiE "composite\.py overlay|composite it over|as an overlay" "$f"; then
    if ! grep -qE "transparent:[[:space:]]*true" "$f"; then
      echo "FAIL $f documents composite.py overlay but does not declare transparent: true"
      fail=1
    fi
  fi
done

exit $fail
