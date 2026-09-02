# Eval — Audio source routing (Phase 5 Step 5.0a)

**What it tests:** whether a scene is correctly resolved to `platform-native` or `elevenlabs` once the
user has picked `elevenlabs` or `mixed` at video level, and whether the prompt is muted accordingly.
LLM behaviour, so these fixtures are the success contract rather than a unit test.

**Rule under test:** `skills/video-gen/SKILL.md` > Step 5.0a, per-scene resolution rule and muting.

**Success threshold:** capability set 4/4. Regression set 4/4. A scene wrongly resolved to
`elevenlabs` when a mouth is visible is the expensive failure — the clip has to be regenerated — so
it counts double when judging a change to the rule.

**How to run:** give a fresh session the video-level answer (`elevenlabs`), one scene description,
and the rule. Ask for the scene's `audio_source` plus whether the prompt carries a speech line.

---

## Capability set

| # | Video-level answer | Scene | Expected `audio_source` | Expected prompt |
|---|---|---|---|---|
| 1 | `elevenlabs` | "Medium close-up, supervisor faces camera and explains the new procedure, face fills about half the frame" | `platform-native` | Keeps `Host says:`. No muting negative. Face over 30% means the platform must speak so the lips match. |
| 2 | `elevenlabs` | "Wide shot of the conveyor line, nobody speaking, narration runs over it" | `elevenlabs` | No speech line at all. Negative block contains `no speech, no voiceover, no dialogue`. SFX and ambient stay. |
| 3 | `elevenlabs` | "Over-the-shoulder from behind the operator, he says one line while looking at the screen, his face is not visible" | `elevenlabs` | No speech line. Mouth is not visible, so nothing has to sync. |
| 4 | `elevenlabs` | "Scene 7: cast-c2 speaks to camera for 3 seconds, then the camera pushes past him to the yard while cast-c1 narrates" | `platform-native` for the dialogue layer, `elevenlabs` for the narration layer | One scene, two layers, sequential and non-overlapping. The prompt carries only cast-c2's line. |

## Regression set

| # | Scene | Expected | The trap |
|---|---|---|---|
| R1 | B-Roll scene, video-level `elevenlabs` | `elevenlabs`, prompt has NO `Voice-over narrator` line | CLAUDE.md's hard rule says every B-Roll needs that line. It applies to `platform-native` only. Adding it here produces two voices. |
| R2 | Face-front dialogue scene, video-level `elevenlabs` | `platform-native`, prompt keeps its speech line | The tempting answer is "user said ElevenLabs, so mute everything". That silently breaks lip-sync. |
| R3 | Video-level `elevenlabs`, and the video has three face-front scenes | mode is reported back as `mixed`, out loud | Resolving quietly is the failure. The user has to learn that some scenes stayed on platform audio. |
| R4 | `elevenlabs` scene, prompt drafted with SFX and ambient removed along with the speech | FAIL | Only SPEECH moves out. Audio is never optional; a silent clip is still a defect. |

---

## Scoring notes

- Two answers per fixture: the `audio_source` value AND what the prompt contains. Both must be right.
- The muting negative is scored verbatim: `no speech, no voiceover, no dialogue`. A paraphrase such as
  "no talking" does not count, because the reviewer check C5 matches the exact string.
- If a fixture starts failing after a rule edit, fix the rule or record why the new answer is better.
  Never edit the fixture to match the new output.
