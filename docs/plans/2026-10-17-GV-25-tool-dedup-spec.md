**Ticket:** GV-25

# GV-25 — Remove overlapping tools found after GV-24

## Design

Source: owner-requested overlap review on 2026-10-17, after v3.21.0 (GV-24) shipped. Owner approved
items #1–#4 below; #5 (`prosody` vs `guide_vo`) and #6 (`keyword_cards.py`, already deleted) need
no change.

### #1 — Screen panels: two pipelines for one job (priority: high)

`skills/video-explainer/SKILL.md` lines ~80–92 and checklist line ~246 still route a panel that
sits on a phone/monitor to Remotion `QuadScreenTracked` (`templates/remotion/lib/quad-screen.tsx`)
fed by `tools/track_screen.py`. That is the pipeline whose failures caused GV-24. `video-gen`
Hard Rule 26, validator V17 and `docs/tool-routing.md` already route to
`python3 -m tools.vidkit screen-insert <clip> <panel> <out> --mode green|track`.

Change: `video-explainer` renders the panel content in Remotion (screen/screencast shot as an
mp4 or PNG), then places it with `vidkit screen-insert`. `QuadScreenTracked` is marked legacy
(header comment + docs), not used by any skill. `track_screen.py` stays only as a way to read
the four `--corners` numbers for `--mode track`; its docs say so.

### #2 — `tools/vidkit/track.py` (`vidkit smooth-track`) is a leftover (priority: medium)

It median-smooths the old box tracks from `track_screen.py`. No skill uses it; only
`docs/vidkit.md`, `docs/tool-routing.md` (screen route) and `tools/registry.json` (entry ~line 868,
screen route tools list ~line 1401) mention it. One-Euro smoothing inside `tools/vidkit/screen.py`
replaced it.

Change: retire it — remove the module, its CLI subcommand in `tools/vidkit/__main__.py`, its tests,
registry entry and route mention; regenerate `docs/tool-routing.md` with
`python3 tools/registry_build.py render`. Check `grep -rn "smooth_track\|smooth-track\|vidkit import.*track\b"`
first; stop if a real caller exists.

### #3 — `cast_voice.mjs` comment is stale; seed only lives there (priority: low)

`tools/vidkit/js/cast_voice.mjs` is a 53-line wrapper over `convertSpans` from
`tools/voice_changer.mjs` (not a duplicate). Its header says `voice_changer.mjs` sends no
`voice_settings`, but `voice_changer.mjs` now has `--stability` / `--style` (line ~64).

Change: fix the comment. Add `--seed N` to `voice_changer.mjs` (sent as the `seed` form field),
so `cast_voice.mjs` is only the per-cast batch runner. Node test for the new flag.

### #4 — `qa_frames.py` re-implements frame tiling (priority: low)

`tools/qa_frames.py` `make_sheet` (lines ~197–215) extracts frames at exact times (incl. the last
frame) and hstacks them; `tools/vidkit/sheet.py` `contact_sheet` samples by fps and cannot hit
exact times.

Change: add `times=None` to `vidkit.sheet.contact_sheet` (exact timestamps when given, current
behaviour otherwise); `qa_frames.make_sheet` calls it. Output file names and the V15 gate stay
identical; existing `tests/py/test_qa_frames.py` must pass unchanged.

### Testing

TDD per item. Gates: `bash tests/run.sh`, `python3 tools/registry_build.py validate --coverage`,
`render --check`, `python3 -m py_compile` on changed `.py`. Docs: CLAUDE.md architecture rows and
changelog, `docs/vidkit.md`. Release as a patch (3.21.1) and bump the gaspol-one marketplace from
the pushed `origin/main` version. No `security-reviewer` (plugin repo).
