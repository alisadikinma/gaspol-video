#!/usr/bin/env bash
# The audio-source decision must be binding, asked before any prompt is written, and
# must mute the prompt when the voice comes from outside the video platform. Two voices
# on one scene is the failure this contract exists to prevent.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
GEN=skills/video-gen/SKILL.md

need() {
  if ! grep -qF "$2" "$1"; then echo "FAIL $3"; fail=1; fi
}

need "$GEN" "audio_source"      "audio_source enum not found in $GEN"
need "$GEN" "platform-native"   "audio_source value platform-native missing in $GEN"
need "$GEN" "elevenlabs"        "audio_source value elevenlabs missing in $GEN"
need "$GEN" "mixed"             "audio_source value mixed missing in $GEN"
need "$GEN" "no speech, no voiceover, no dialogue" "muting negative string missing in $GEN"
need "$GEN" "30%"               "face >30% resolution rule missing in $GEN"

# the question must come BEFORE platform selection, not after
q=$(grep -n "Step 5.0a" "$GEN" | head -1 | cut -d: -f1)
p=$(grep -n "Step 5.0:" "$GEN" | head -1 | cut -d: -f1)
if [ -z "$q" ] || [ -z "$p" ]; then
  echo "FAIL cannot locate Step 5.0a and Step 5.0 in $GEN"
  fail=1
elif [ "$q" -ge "$p" ]; then
  echo "FAIL Step 5.0a (audio source) must come before Step 5.0 (platform selection): 5.0a at $q, 5.0 at $p"
  fail=1
fi

# VO-first: duration must be driven by measured audio, not word count
if ! grep -qiE "measured|vo-manifest" "$GEN"; then
  echo "FAIL $GEN does not tie clip duration to measured VO length"
  fail=1
fi

need agents/video-prompt-reviewer.md "C5." "validator check C5 not defined in the prompt reviewer"
need skills/video-validate/SKILL.md  "Check V13" "video-validate has no V13 double-audio check"
need reference/image-video-gen/09-voice-consistency-workflow.md "gen_vo.mjs" "Path B still describes a manual process, does not point at the tool"

exit $fail
