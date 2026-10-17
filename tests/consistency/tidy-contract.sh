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

# Archive happens inside the render step, after a successful render: every "move the returned
# local file" sentence must have `archive --file` within the six lines before it.
for s in video-image video-gen; do
  f="skills/$s/SKILL.md"
  anchors="$(grep -ciF 'move the returned local file' "$f")"
  if [ "$anchors" -lt 1 ]; then
    echo "FAIL $f has no 'move the returned local file' render step"
    fail=1
  fi
  while IFS=: read -r ln _; do
    start=$(( ln > 6 ? ln - 6 : 1 ))
    if ! sed -n "${start},${ln}p" "$f" | grep -qF -- 'archive --file'; then
      echo "FAIL $f:$ln render step moves the new file without \`archive --file\` first"
      fail=1
    fi
  done < <(grep -niF 'move the returned local file' "$f")
done
# Allowed tool-made subfolders are named in the folder contract.
for f in reference/post-production/10-post-production-pipeline.md skills/video-image/SKILL.md \
         skills/video-gen/SKILL.md skills/video-post/SKILL.md skills/video-explainer/SKILL.md; do
  for sub in 'ref/sumber/' 'vo/native/' 'vo/master/' 'output/stems/'; do
    need "$f" "$sub" "$f folder contract missing allowed subfolder \`$sub\`"
  done
done
# No instruction may create a forbidden subfolder. Only the "Instead of | Write" table may show one.
bad="$(grep -rnE '(clips|keyframes|ref|vo|sfx)/_' skills reference agents templates \
  | grep -vE '^reference/post-production/10-post-production-pipeline\.md:[0-9]+:\| `')"
if [ -n "$bad" ]; then
  echo "FAIL forbidden subfolder path outside the Instead-of table:"
  echo "$bad"
  fail=1
fi

exit $fail
