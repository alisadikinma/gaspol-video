#!/usr/bin/env bash
# No credential may be COMMITTED. Scans tracked files only (git ls-files), because that
# is exactly the boundary that matters: .env holds real keys and is ignored on purpose.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

# a key line with an actual value after the '=' (empty ones are documentation)
while IFS= read -r hit; do
  [ -n "$hit" ] || continue
  case "$hit" in
    *".env.example"*) continue ;;   # documents names, never values
    *"tests/consistency/no-secrets.sh"*) continue ;;  # this file names the patterns
    docs/plans/*) continue ;;        # design docs discuss the key NAMES in prose
  esac
  echo "FAIL committed key: $hit"
  fail=1
done <<< "$(git ls-files -z | xargs -0 grep -nE '(ELEVENLABS_API_KEY|ASSEMBLYAI_API_KEY|FAL_KEY|GEMINI_API_KEY)[[:space:]]*=[[:space:]]*[A-Za-z0-9_./+-]{12,}' 2>/dev/null || true)"

# an ElevenLabs voice id is ~20 chars of base62; the repo must name the ENV VAR, never the id
while IFS= read -r hit; do
  [ -n "$hit" ] || continue
  case "$hit" in
    *"tests/consistency/no-secrets.sh"*) continue ;;
    docs/plans/*) continue ;;
  esac
  echo "FAIL hardcoded voice id: $hit"
  fail=1
done <<< "$(git ls-files -z | xargs -0 grep -nE 'voice_id[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9]{18,24}["'"'"']?' 2>/dev/null || true)"

exit $fail
