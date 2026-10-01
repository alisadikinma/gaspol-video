#!/usr/bin/env bash
# v3.8.0: brainstorm must ask what the customer sells and collect real photos; the
# script phase must consume them; Phase 4A must refuse to start without them.
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

B=skills/video-brainstorm/SKILL.md
need "$B" "Step 1.2e"                 "video-brainstorm lost Step 1.2e (customer business profile)"
need "$B" "ref/biz-product-"          "video-brainstorm does not name ref/biz-product-*"
need "$B" "ref/biz-site-"             "video-brainstorm does not name ref/biz-site-*"
need "$B" "generated-approved"        "video-brainstorm lost the approved-fallback flag"
need "$B" "## Business Profile"       "strategic-brief template has no Business Profile section"

S=skills/video-script/SKILL.md
need "$S" "Business Reference Photos" "video-script 3.5.1 does not read Business Reference Photos"
need "$S" "never invent a product"    "video-script does not forbid inventing a product"

I=skills/video-image/SKILL.md
need "$I" "Business Profile gate"     "video-image has no Business Profile prerequisite"
need "$I" "FROM \`ref/biz-site-"      "video-image Rule 40 missing (env derives from customer photos)"

# pre-existing hooks must survive
need "$B" "Step 1.2d" "pre-existing Step 1.2d disappeared"
need "$S" "Phase 3.5 is HARD BLOCK" "pre-existing Phase 3.5 hard block disappeared"

exit $fail
