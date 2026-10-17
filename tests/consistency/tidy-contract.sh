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
  # Anchored on the folder-contract list itself: a bare "sfx/" also matches media/sfx/library paths.
  need "skills/$s/SKILL.md" '`vo/` `sfx/`' "skills/$s/SKILL.md folder-contract paragraph missing \`sfx/\`"
done
# Only the generated table counts, not prose elsewhere in the file.
routes_table="$(sed -n '/<!-- registry:routes:begin -->/,/<!-- registry:routes:end -->/p' docs/tool-routing.md)"
for needle in "vidkit tidy" "archive --file"; do
  if ! grep -qF -- "$needle" <<<"$routes_table"; then
    echo "FAIL docs/tool-routing.md generated table missing \`$needle\`"
    fail=1
  fi
done
need tools/registry.json '"tools/vidkit/tidy.py"' "tools/registry.json missing \"tools/vidkit/tidy.py\""
need tools/registry.json '"render-archive"' "tools/registry.json missing \"render-archive\""
need reference/post-production/10-post-production-pipeline.md "### 2.4" "pipeline doc missing ### 2.4"

exit $fail
