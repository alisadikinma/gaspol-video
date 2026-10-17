#!/usr/bin/env bash
# v3.19.0: archive before re-render, vidkit tidy for cleanup; skills, docs and registry agree.
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

for s in video-image video-gen; do
  need "skills/$s/SKILL.md" "archive --file" "skills/$s/SKILL.md missing \`archive --file\`"
done
for s in video-image video-gen video-post video-explainer; do
  need "skills/$s/SKILL.md" "vidkit tidy" "skills/$s/SKILL.md missing \`vidkit tidy\`"
  need "skills/$s/SKILL.md" "sfx/" "skills/$s/SKILL.md folder-contract paragraph missing \`sfx/\`"
done
need docs/tool-routing.md "vidkit tidy" "docs/tool-routing.md table missing \`vidkit tidy\`"
need docs/tool-routing.md "archive --file" "docs/tool-routing.md table missing \`archive --file\`"
need tools/registry.json '"tools/vidkit/tidy.py"' "tools/registry.json missing \"tools/vidkit/tidy.py\""
need tools/registry.json '"render-archive"' "tools/registry.json missing \"render-archive\""
need reference/post-production/10-post-production-pipeline.md "### 2.4" "pipeline doc missing ### 2.4"

exit $fail
