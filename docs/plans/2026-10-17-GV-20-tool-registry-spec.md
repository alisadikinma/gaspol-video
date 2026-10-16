# GV-20: Tool registry, duplicate gate, and write-time reminder hook

**Ticket:** GV-20

## Problem

`tools/` and `tools/vidkit/` hold about 60 tools for image, video and audio work. Two things are
not guaranteed today:

1. **Uniqueness.** Nothing checks that a new tool does not repeat an old one. Measured 2026-10-17:
   16 files call `ffprobe` themselves although `vidkit.ff.probe` exists; `probe_clips.py` overlaps
   `vidkit probe`.
2. **Routing.** "Which tool for which job" lives only in `docs/tool-routing.md`, a hand-written table.
   Four files are missing from it (`check_overlay_strings.py`, `probe_clips.py`,
   `vidkit/gates.py`, `vidkit/patch.py`). `tests/consistency/tools-index.sh` checks names against
   `CLAUDE.md` only, never against the routing table. No hook reminds the agent to read the table
   before writing a new script.

## Design

Decisions approved 2026-10-17: registry + gate tests + write-time reminder hook; hook fires on
file writes only; hook reminds, never blocks.

### 1. Registry `tools/registry.json`

Single source of truth. One entry per tool file or vidkit module:

| Field | Meaning |
|---|---|
| `id` | file path relative to plugin root |
| `purpose` | one sentence, what it is for |
| `tasks` | list of task tags (e.g. `probe`, `concat`, `subtitles`) |
| `phase` | pipeline phase, or `shared` |
| `replaces` | tools this one supersedes (may be empty) |

`docs/tool-routing.md` table is generated from the registry by a small script
(`tools/registry_build.py`). The hand-written intro and the "When no tool fits" section stay as
fixed text around the generated block.

### 2. Gate tests (`tests/consistency/tool-registry-contract.sh` + `tests/py/test_registry.py`)

- Every file in `tools/*.py`, `tools/*.mjs`, `tools/vidkit/*.py`, `tools/vidkit/js/*.mjs` has a
  registry entry (except `__init__.py`, `_venv.py`). No entry points at a missing file.
- The generated routing block equals the committed one (no drift).
- No `ffprobe` call outside `tools/vidkit/ff.py`, except an explicit allowlist in the registry,
  each with a written reason.
- No two entries share the same `tasks` set and the same `phase` unless one lists the other in
  `replaces` or both carry a written `distinct_because`.
- The 16 current `ffprobe` callers move to `vidkit.ff.probe`. `probe_clips.py` is merged into
  vidkit or given a distinct task, decided during planning with a test proving behaviour is kept.

### 3. Reminder hook (`hooks/hooks.json`, `hooks/tool-reminder.sh`)

PreToolUse on `Write` and `Edit`. Fires only when all hold:

- file extension is `.py`, `.mjs` or `.sh`;
- path is outside `tools/`, `tests/`, `templates/`;
- content contains `ffmpeg`, `ffprobe` or `remotion`.

Action: match the content against registry `tasks` and `purpose` words, and emit the three closest
tools as additional context, plus the rule "none fits: add to vidkit with a test and a registry
row". Never blocks. If the registry is unreadable, the hook exits 0 silently and logs one line to
stderr.

## Out of scope

Semantic search, blocking, cross-plugin duplicate checks (`gaspol-catalog` has its own `deckkit`),
rewriting tools beyond swapping the `ffprobe` call.

## Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Registry | `tools/registry.json` | no | new; filled once by hand, about 60 entries |
| Routing table | generated from registry | table exists, hand-written | generator is new |
| Gate tests | `tests/consistency/`, `tests/py/` | pattern exists (`tools-index.sh`) | new files |
| Hook | `hooks/hooks.json` | SessionStart only | add PreToolUse entry |

## Testing

- Registry covers every tool (fails on a new unregistered file).
- Generated block drift test.
- `ffprobe` outside `ff.py` fails the gate; allowlist entries need a reason.
- Hook: table-driven test feeding sample tool-call JSON; asserts fires/no-fire and the three
  suggested tools; asserts exit 0 on a broken registry.
- Existing `bash tests/run.sh` stays green after the 16-file `ffprobe` swap.

## Risks

- Filling about 60 `purpose` lines is manual and one-time.
- Hook keyword match can suggest a weak tool; mitigated because it only reminds.

## Amendments (planning, 2026-10-17)

- Routes live in `tools/registry.json` (`tools[]` + `routes[]` + `ffprobe_allow[]`), not in the markdown table; the table is generated.
- The ffprobe migration is scoped to 2 callers (`check_vo_duration.py`, `track_screen.py`). The remaining callers are allowlisted in `ffprobe_allow` with written reasons (17 entries at release).
- `probe_clips.py` is kept as its own tool with a `distinct_because` entry.
- The reminder hook is the `suggest` and `hook` subcommands of `registry_build.py`, wrapped by `hooks/tool-reminder.sh`.
