#!/usr/bin/env bash
# GV-17 Phase F: KineticOverlay template contract. No tsc in this repo, so the structure the
# render depends on is pinned here: five layer markers in order, determinism rules, brand-only
# colours, and the icon list shared with tools/overlay_plan.py.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

T=templates/remotion/Overlay.template.tsx
F=templates/remotion/lib/overlay-fx.tsx
for f in "$T" "$F"; do
  if [ ! -f "$f" ]; then echo "FAIL $f missing"; fail=1; fi
done
[ "$fail" -ne 0 ] && exit 1

prev=0
for m in 'L1 clip' 'L2 behind' 'L3 person' 'L4 front' 'L5 source'; do
  n=$(grep -nF -- "{/* $m */}" "$T" | head -1 | cut -d: -f1)
  if [ -z "$n" ]; then echo "FAIL $T lacks layer marker {/* $m */}"; fail=1; continue; fi
  if [ "$n" -le "$prev" ]; then echo "FAIL layer marker '$m' is out of order"; fail=1; fi
  prev=$n
done

for f in "$T" "$F"; do
  if grep -nE 'useState|useEffect|setTimeout|Math\.random' "$f" >/dev/null; then
    echo "FAIL $f uses a banned non-deterministic API"; fail=1
  fi
  if grep -nE '#[0-9a-fA-F]{6}' "$f" >/dev/null; then
    echo "FAIL $f has a hex colour literal (use brand.ts)"; fail=1
  fi
done

grep -qF 'KineticOverlay' "$T" || { echo "FAIL $T lacks the KineticOverlay id"; fail=1; }

js=$(python3 -c "
import re
src = open('$F').read()
m = re.search(r'export const ICONS[^=]*=\s*\{(.*?)\n\};', src, re.S)
print(' '.join(sorted(re.findall(r'^\s{2}(\w+)\s*:', m.group(1), re.M))) if m else '')
")
py=$(python3 -c "
import re
src = open('tools/overlay_plan.py').read()
m = re.search(r'^ICONS\s*=\s*\((.*?)\)', src, re.M)
print(' '.join(sorted(re.findall(r'\"(\w+)\"', m.group(1)))) if m else '')
")
if [ -z "$js" ] || [ "$js" != "$py" ]; then
  echo "FAIL ICONS differ: overlay-fx.tsx [$js] vs overlay_plan.py [$py]"; fail=1
fi

B=templates/remotion/brand.json
grep -qF '"highlight"' "$B" || { echo "FAIL $B lacks highlight"; fail=1; }
grep -qF '"scriptFont"' "$B" || { echo "FAIL $B lacks scriptFont"; fail=1; }
grep -qE 'export const FONT_SCRIPT' templates/remotion/lib/brand.ts || { echo "FAIL brand.ts does not export FONT_SCRIPT"; fail=1; }

exit $fail
