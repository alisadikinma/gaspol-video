#!/usr/bin/env bash
# v3.9.0: brainstorm must ask delivery points/vehicles and the company uniform; the
# script phase must cover every vehicle class; image must build the assets; the
# reviewer must fail a customer employee out of uniform or a missing vehicle class.
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
need "$B" "### Delivery Points & Vehicles" "brainstorm has no Delivery Points & Vehicles section"
need "$B" "### Company Uniform"            "brainstorm has no Company Uniform section"
need "$B" "## Company Uniform"             "brainstorm does not put a Company Uniform block in cast-profile.md"
need "$B" "Appears in video"               "Delivery Points table lost the appears-in-video column"
need "$B" "logo exactly as ref/brand-"     "uniform phrase does not lock the logo to the real logo file"
need "$B" "14. **(v3.9.0)"                 "brainstorm Hard Rule 14 missing"
need "$B" "15. **(v3.9.0)"                 "brainstorm Hard Rule 15 missing"

S=skills/video-script/SKILL.md
need "$S" "ref/vehicle-{class}.png"        "video-script manifest does not require vehicle assets per class"
need "$S" "excludes trucks"                "video-script does not stop on a truck at a truck-excluded point"
need "$S" "costume-uniform-{client}.png"   "video-script manifest does not require the uniform ref"

I=skills/video-image/SKILL.md
need "$I" "Vehicle + uniform gate"         "video-image has no vehicle/uniform prerequisite"
need "$I" "41. **(v3.9.0)"                 "video-image Rule 41 missing"
need "$I" "42. **(v3.9.0)"                 "video-image Rule 42 missing"
need "$I" "costume-uniform-<client>.png"   "video-image does not generate the uniform ref"

R=agents/video-prompt-reviewer.md
need "$R" "C13."                           "reviewer has no check C13"
need "$R" "Company Uniform"                "reviewer does not check the uniform"
need "$R" "vehicle class"                  "reviewer does not check vehicle classes in scene-plan"

# pre-existing hooks must survive
need "$B" "Step 1.2e" "Step 1.2e disappeared"
need "$I" "Business Profile gate" "v3.8.0 Business Profile gate disappeared"

exit $fail
