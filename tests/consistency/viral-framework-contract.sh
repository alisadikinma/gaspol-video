#!/usr/bin/env bash
# GV-19 Phase D: the viral framework F12 exists with its seven stages, every threshold is
# tagged as course advice, and the script skill, engine agent and validator point at it.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
F12="reference/storytelling_script_gen/F12_Viral_Framework.md"

if [ ! -f "$F12" ]; then
  echo "FAIL: $F12 does not exist"
  exit 1
fi

n=0
for stage in "Topic research" "Hook" "Script" "Edit" "Caption and hashtags" "Posting" "Analytics"; do
  n=$((n + 1))
  grep -qE "^## Stage $n: $stage" "$F12" || { echo "FAIL: $F12 lacks heading '## Stage $n: $stage'"; fail=1; }
done

for t in "at least 20%" "at least 50% of the video length" "views above 100000"; do
  grep -F "$t" "$F12" | grep -qF 'source: course' || { echo "FAIL: threshold '$t' not tagged source: course"; fail=1; }
done

for tag in "[DATA]" "[TAFSIRAN]" "114215f6" "Worked example" "exit code"; do
  grep -qF "$tag" "$F12" || { echo "FAIL: $F12 lacks '$tag'"; fail=1; }
done
grep -qi "unverified claim\|nobody has verified" "$F12" || { echo "FAIL: title-formula guard about unverified claims on a real person missing"; fail=1; }

for f in skills/video-script/SKILL.md agents/video-engine-agent.md; do
  for needle in "F12_Viral_Framework.md" "viral_checklist.py"; do
    grep -qF "$needle" "$f" || { echo "FAIL: $f does not mention $needle"; fail=1; }
  done
done
grep -qF "S10" skills/video-validate/SKILL.md || { echo "FAIL: skills/video-validate/SKILL.md lacks check S10"; fail=1; }
grep -qF "## Viral Checklist" skills/video-script/SKILL.md || { echo "FAIL: video-script template lacks the '## Viral Checklist' block"; fail=1; }

[ "$fail" -eq 0 ] && echo "PASS viral-framework-contract"
exit "$fail"
