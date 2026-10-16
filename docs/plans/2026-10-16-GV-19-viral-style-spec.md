# GV-19 — Viral style (Samuel Christ reference) + viral framework

**Ticket:** GV-19
**Status:** design, awaiting spec review. Phase 1 is a study, so the later phases may change after it.
**Sister ticket:** GV-18 (master quality).

## Why

The owner likes the animation, SFX and music of a creator's Shorts and wants the same style, plus a viral-video framework. Two NotebookLM notebooks feed this: the course notebook (`Seefluencer AI Mentor`, framework) and a notebook built from 24 transcripts of the reference channel (`SAMUEL-STYLE 2026-10`). Imitating a style, not copying content: no footage, voice, face or script is reused.

## Measured facts (12 Shorts downloaded and measured; 1 further download failed)

- The "animation" is mostly **overlay on a single take**. The 272k-view short has 0 camera cuts; the others 2–42.
- Overlay vocabulary seen: top step counter ①–⑤ with the active number lit; sticker icons beside the spoken phrase; red warning triangles + red vignette on danger words; falling money on "wealth"; two-tier captions (small white, big neon-green keyword); red circle on screen recordings; blur transitions; a corner "full video" chip.
- Experiment format (ant story): close-ups of hands and props, centred serif captions, short cutaways to the speaker.
- Integrated loudness -24.1 to -7.8 LUFS over 12 clips (median -11.8, mean -12.2; the 11 clips other than one quiet outlier lie between -13.6 and -7.8, mean -11.1). Mostly louder than this plugin's -14 target. Figures in `docs/evals/short-form-loudness-measurement.md`.
- Script patterns (transcripts, per NotebookLM, `[DATA]` vs `[TAFSIRAN]` separated): direct hook, title = emotion + public figure + large amount, open-ended ending "Dan itulah..." that loops into the hook.

## Not yet measured (phase 1 exists for this)

SFX types and timing, music genre/tempo, how SFX and music relate to cuts and words. Only loudness was measured. No listening analysis has been done.

## Phases

| # | Phase | Done when |
|---|---|---|
| 1 | Audio & timing study: from the downloaded clips, measure SFX onset times against words and cuts, music tempo/energy per segment. Written to `docs/` as evidence. | Findings table with numbers; each claim marked data or interpretation |
| 2 | Overlay vocabulary into `KineticOverlay`: sticker-icon set, step counter, red-flash/vignette, falling-object burst, two-tier caption preset. Brand tokens, not hardcoded green. | Rendered still at each cue (existing QA convention); `overlay_plan.py` still refuses text >50% of speech |
| 3 | Retention gate: script and edit checks — no static frame over 3.0 s, hook within 3 s, foreshadow by 3–6 s, b-roll matches the spoken word, BGM not covering voice. Course numbers are defaults, flagged as course advice, overridable. | `video-validate --retention` lists pass/fail per rule on a real cut |
| 4 | Viral framework in `video-script`: 7 stages (topic research, hook, script, edit, caption, posting, analytics) with a pass/fail checklist; title formula; loop ending; analytics thresholds (watched-full ≥20%, avg watch ≥50%, replicate winners >100k views) | A generated script carries the filled checklist |
| 5 | Wrap: docs, `tool-routing.md`, NOTICE, tests, version bump | `bash tests/run.sh` green |

## Constraints and risks

- Course figures (Montserrat 15–18, centre position, 1–3 s cut interval) are a course's advice, not platform data. Ship as presets with a "source: course" tag.
- Downloaded reference clips stay in a scratch folder, never in the repo.
- Reuse before building: `KineticOverlay`, `overlay_plan.py`, `gen_captions.py`, `plan_motion.py` already exist. Extend, do not duplicate.
- Retention gate must not become a quality ceiling: it reports, the owner decides.

## Out of scope

GV-18 items. Auto-posting and analytics pulls (`yt_stats.py` exists and needs an OAuth client not yet created).
