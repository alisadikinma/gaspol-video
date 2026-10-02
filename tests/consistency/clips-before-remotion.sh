#!/usr/bin/env bash
# v3.9.2: Remotion shots are built after the VEO clips of their kelompok, never before.
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

need skills/video-gen/SKILL.md "24. **(v3.9.2) VEO clips first, Remotion after.**" "video-gen Rule 24 missing"
need skills/video-gen/SKILL.md "only now that this kelompok's VEO clips are rendered" "video-gen K.4 does not wait for the clips"
need skills/video-explainer/SKILL.md "The VEO clips of this kelompok are rendered first" "video-explainer prerequisite does not require clips first"
need skills/video-full/SKILL.md "No standalone Remotion step" "video-full still has a Remotion step before video-gen"
need reference/post-production/10-post-production-pipeline.md "Remotion (Phase 4.5, AFTER clips)" "pipeline diagram does not put Remotion after clips"
if grep -q "independent of clips" reference/post-production/10-post-production-pipeline.md; then
  echo "FAIL pipeline doc still says Remotion is independent of clips"
  fail=1
fi

exit $fail
