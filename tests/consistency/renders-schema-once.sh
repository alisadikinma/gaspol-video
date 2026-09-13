#!/usr/bin/env bash
# renders.json (the in-session render ledger) must be documented exactly ONCE, in
# reference/post-production/10-post-production-pipeline.md — Phase 4/5 skills point to it
# instead of restating the schema. Spec §8.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

REF10=reference/post-production/10-post-production-pipeline.md
IMAGE_SKILL=skills/video-image/SKILL.md
GEN_SKILL=skills/video-gen/SKILL.md

if ! grep -qF '"prompt_sha256"' "$REF10"; then
  echo "FAIL renders.json schema (prompt_sha256) not documented in $REF10"
  fail=1
fi

if ! grep -qF 'renders.json' "$IMAGE_SKILL"; then
  echo "FAIL $IMAGE_SKILL does not reference renders.json at all"
  fail=1
fi
if ! grep -qF 'renders.json' "$GEN_SKILL"; then
  echo "FAIL $GEN_SKILL does not reference renders.json at all"
  fail=1
fi

for f in "$IMAGE_SKILL" "$GEN_SKILL"; do
  if grep -qF '"prompt_sha256"' "$f"; then
    echo "FAIL $f restates the renders.json schema instead of pointing to $REF10"
    fail=1
  fi
done

exit $fail
