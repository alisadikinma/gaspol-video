#!/usr/bin/env bash
# A speaking character carries its own voice, and the voice id lives in the user's env,
# never in this repo. The plugin is client-agnostic by contract.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
need() { if ! grep -qF "$2" "$1"; then echo "FAIL $3"; fail=1; fi; }

CP=reference/creator-profile-system.md
need "$CP" "VOICE:"        "VOICE: block not defined in $CP"
for field in provider voice_env model settings source description; do
  need "$CP" "$field" "VOICE: block is missing the $field field in $CP"
done
need "$CP" "ELEVENLABS_VOICE_C" "voice_env naming convention missing in $CP"

need reference/post-production/11-voice-cast-and-vo.md "native+changer" \
     "11-voice-cast-and-vo.md does not document the native+changer source"
need .env.example "ELEVENLABS_VOICE_NARRATOR" ".env.example does not document the narrator voice var"
need .env.example "ASSEMBLYAI_API_KEY"        ".env.example does not document the ASR key"
need agents/video-prompt-reviewer.md "C8." "validator check C8 not defined in the prompt reviewer"
need skills/video-validate/SKILL.md  "Check V14" "video-validate has no V14 voice-profile check"
need skills/video-brainstorm/SKILL.md "VOICE" "cast builder never asks for a voice"

# .env.example documents NAMES only: no line may carry a value
while IFS= read -r line; do
  case "$line" in
    ''|'#'*) continue ;;
    *=) continue ;;
    *=*) echo "FAIL .env.example carries a value: ${line%%=*}=..."; fail=1 ;;
  esac
done < .env.example

exit $fail
