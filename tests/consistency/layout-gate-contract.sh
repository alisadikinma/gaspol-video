#!/usr/bin/env bash
# GV-23 Phase H: the layout gate is registered with real routes, documented in video-validate,
# and required before "final" in video-post and video-package; the profile file validates.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
need() { if ! grep -qF -- "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

python3 - <<'PY' || fail=1
import json, sys
reg = json.load(open("tools/registry.json"))
ids = {t["id"]: t for t in reg["tools"]}
bad = 0
for tid in ("tools/layout_gate.py", "tools/face_box.py", "tools/vidkit/layout.py", "tools/vidkit/title.py"):
    t = ids.get(tid)
    if t is None:
        print(f"FAIL registry has no {tid}"); bad = 1; continue
    r = t.get("internal_reason", "")
    if "wiring phase" in r or "Phase H" in r:
        print(f"FAIL {tid} internal_reason is still a placeholder"); bad = 1
uses = " ".join(r["use"] for r in reg["routes"])
for needle in ("layout_gate.py check", "tools.vidkit title", "face_box.py"):
    if needle not in uses:
        print(f"FAIL no route uses {needle}"); bad = 1
sys.exit(bad)
PY

python3 - <<'PY' || fail=1
import json, sys
sys.path.insert(0, ".")
from tools.vidkit import layout
problems = layout.validate(json.load(open("media/layout-profiles.json")))
for p in problems:
    print("FAIL layout-profiles.json:", p)
sys.exit(1 if problems else 0)
PY

V=skills/video-validate/SKILL.md
need "$V" '## Layout Validation (`--layout`)' "video-validate has no --layout section"
need "$V" "layout_gate.py check" "video-validate --layout does not run layout_gate.py check"
need "$V" "Exit 2" "video-validate --layout does not document exit 2"
P=skills/video-post/SKILL.md
need "$P" "layout_gate.py check" "video-post --final does not call layout_gate.py check"
need "$P" "not final until" "video-post does not block final on the layout gate"
K=skills/video-package/SKILL.md
need "$K" "vidkit title" "video-package does not stamp the 9:16 title with vidkit title"
need "$K" "layout_gate.py check" "video-package does not call layout_gate.py check"
R=skills/video-repackage/SKILL.md
need "$R" "vidkit title" "video-repackage 6b does not list vidkit title"
need "$R" "layout_gate.py" "video-repackage 6b does not list layout_gate.py"
need "$R" "short-organic" "video-repackage 6b does not state the karaoke default profile"
exit $fail
