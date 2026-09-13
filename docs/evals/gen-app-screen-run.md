# `gen_app_screen.py` real run — capture and mock re-run (GV-2 plan-verifier fix)

The plan-verifier flagged that the capture/mock runs recorded for this ticket could not be
trusted from memory. This is a fresh, actually-executed re-run of both subcommands, done from
this worktree against the shared venv (`~/.gaspol-video/venv`), with exact commands, output file
listing, manifest excerpts, and what the resulting PNGs show.

## capture — fresh scratch project, `https://example.com`

A brand-new scratch project directory was created so the capture could not be confused with any
earlier run:

```
PROJ=<scratchpad>/gv2-capture-rerun
mkdir -p "$PROJ/screens" "$PROJ/ref"
```

`$PROJ/screens/screens.json`:

```json
{
  "viewport": [1920, 1080],
  "device_scale": 1,
  "capture": {
    "base_url": "https://example.com",
    "steps": [
      {"goto": "/"},
      {"wait": 500},
      {"shot": "example-home"}
    ]
  }
}
```

Command:

```
python3 tools/gen_app_screen.py capture "$PROJ"
```

Output:

```
step 00 goto https://example.com/
step 01 wait 500
shot [01] ui-example-home.png
captured 1 screen(s)
```

Exit code: `0`.

### Output files

```
$PROJ/ref/ui-example-home.png   21210 bytes
```

### `screens/manifest.json` after the run

```json
{
  "screens": [
    {
      "name": "example-home",
      "file": "ui-example-home.png",
      "url_label": "",
      "title": "",
      "source": "capture",
      "simulated": false,
      "captured_at": "2026-09-13T10:20:30Z"
    }
  ]
}
```

### What the image shows

`ui-example-home.png` is a screenshot of the real `example.com` page: the "Example Domain"
heading, the standard explanatory paragraph, and the "Learn more" link, rendered on a plain
light-grey background at 1920x1080 (the page content sits in the upper-left, the rest of the
viewport is empty page background — expected for this particular page). This matches what
`https://example.com` actually serves; the capture is real, not a placeholder.

## mock — existing `gv2-remotion` project, `anpr-dashboard` (2 states)

Re-ran `mock` against the pre-existing scaffolded workspace (`shots/` already had
`node_modules` installed and the `ExampleDashboardScreen.tsx` component from the earlier ticket
work) instead of building a new one, per the orchestrator's instruction:

```
PROJ=<scratchpad>/gv2-remotion
python3 tools/gen_app_screen.py mock "$PROJ"
```

Output:

```
mock anpr-dashboard/initial -> ref/ui-anpr-dashboard-initial.png
mock anpr-dashboard/plate-detected -> ref/ui-anpr-dashboard-plate-detected.png
rendered 2 mock screen(s)
```

Exit code: `0`.

### Output files

```
$PROJ/ref/ui-anpr-dashboard-initial.png          72847 bytes
$PROJ/ref/ui-anpr-dashboard-plate-detected.png   73584 bytes
```

Both PNGs were rewritten with a fresh `captured_at` timestamp (`10:20:40Z`) — the render is not
cached from the earlier ticket run.

### What the images show

`ui-anpr-dashboard-initial.png`: a dark-themed "Antrean Gerbang" (gate queue) dashboard, "Gerbang
3" subtitle, a two-row table (`Plat Nomor` / `Estimasi Antre` / `Status`) showing plates
`B 1234 XYZ` (6 menit, status "menunggu") and `D 5678 ABC` (8 menit, status "menunggu") — both
rows in the same neutral dark row colour, no highlight.

`ui-anpr-dashboard-plate-detected.png`: the identical layout, but the `B 1234 XYZ` row is now
highlighted (a warm brown/amber row background) and its Status cell shows an amber
"TERDETEKSI" pill instead of "menunggu" — the second state correctly shows the plate-detection
event the state name promises, and it is a real difference from the first render, not a
duplicate frame.

### `screens/manifest.json` after the run — a real bug found, not from memory

The resulting manifest is **wrong**, and this is worth recording rather than smoothing over:

```json
{
  "screens": [
    {
      "name": "anpr-dashboard",
      "file": "ui-anpr-dashboard-plate-detected.png",
      "url_label": "anpr.client.co.id/gate",
      "title": "Gate Monitor",
      "source": "mock",
      "simulated": true,
      "component": "ExampleDashboardScreen",
      "state": "plate-detected",
      "data_key": "anpr-dashboard",
      "captured_at": "2026-09-13T10:20:40Z"
    },
    {
      "name": "anpr-dashboard",
      "file": "ui-anpr-dashboard-plate-detected.png",
      "url_label": "anpr.client.co.id/gate",
      "title": "Gate Monitor",
      "source": "mock",
      "simulated": true,
      "component": "ExampleDashboardScreen",
      "state": "plate-detected",
      "data_key": "anpr-dashboard",
      "captured_at": "2026-09-13T10:20:40Z"
    }
  ]
}
```

The `initial` state entry is gone entirely, and the `plate-detected` entry is duplicated. The
PNG files on disk are both correct (confirmed above by reading them), so this is a manifest
bookkeeping bug, not a render bug. The cause is `merge_manifest()` in `tools/gen_app_screen.py`:
it keys `new_by_name` by `entry["name"]` alone, and a single mock screen with multiple `states`
produces multiple manifest entries that all share the same `name` (`anpr-dashboard`). The dict
comprehension `{e["name"]: e for e in new_entries}` collapses them to whichever state came last
(`plate-detected`), and the merge loop then re-inserts that same winning entry once per existing
entry that shared the name, which is how a second copy appears instead of the first getting
restored.

This bug reproduced on any repeat `mock` run of a screen with 2+ states.

**Fixed in the same ticket.** `merge_manifest()` now keys by `(name, state)` and collapses
duplicates that the old name-only merge had already written. Regression tests:
`test_rerun_of_multi_state_mock_keeps_every_state`, `test_duplicates_left_by_old_merge_collapse`.
Verified on the same real project: starting from the corrupted manifest above, two consecutive
`python3 tools/gen_app_screen.py mock <project>` runs left exactly
`[('anpr-dashboard', 'plate-detected'), ('anpr-dashboard', 'initial')]`.
