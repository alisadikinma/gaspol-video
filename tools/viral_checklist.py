#!/usr/bin/env python3
"""Viral-framework checklist gate and analytics verdict (GV-19, framework F12).

    python3 tools/viral_checklist.py check <av-script.md>
    python3 tools/viral_checklist.py rate  <packaging/calibration.json>
    python3 tools/viral_checklist.py timeline <av-script.md>

`check` reads the `## Viral Checklist` block of an av-script.md: a table
`| Stage | Item | Verdict |` with one row per item of the 7 stages. Verdict is `PASS`,
`FAIL: reason`, `N/A: reason` or `PENDING: reason`. Exit 0 = every item decided, 1 = at least
one problem (each printed on its own line), 2 = the file could not be read.
`PENDING` is legal only for posting and analytics: they happen after the script is approved.

`rate` turns the analytics a published video produced into a verdict against the course
thresholds. A missing figure gives `unknown` and names the key; it is never guessed.

`timeline` (F13) reads the A/V table's `Tahap` and `Detik` columns and checks the short-form
order Thumbnail (optional), Hook, Foreshadow, Body, CTA, with Hook ending by 3 s and Foreshadow
by 6 s, plus `timeline_tolerance_s` from media/layout-profiles.json. Exit 0 = OK, 1 = problems,
2 = the file is unreadable or has no `Tahap`/`Detik` columns.

Stages, item ids and thresholds mirror reference/storytelling_script_gen/F12_Viral_Framework.md
(tests/py/test_viral_checklist.py asserts every item id appears there). The numbers are course
advice, not platform data.
"""
import argparse
import json
import re
import sys
from pathlib import Path

STAGES = ("topic research", "hook", "script", "edit", "caption", "posting", "analytics")

ITEMS = {
    "topic research": ["specific-niche", "viral-factor", "market-demand"],
    "hook": ["no-greeting", "visual-hook", "honest-promise", "title-formula", "person-claim-verified"],
    "script": ["killer-structure", "foreshadow", "tight-body", "chat-tone", "loop-ending"],
    "edit": ["cut-every-1-3s", "contextual-broll", "captions-safe-zone", "audio-clean"],
    "caption": ["caption-type", "hashtag-3-tier", "invites-interaction"],
    "posting": ["omnipresence", "custom-cover", "music-licence"],
    "analytics": ["benchmarks", "outlier-identified", "replicate-winner"],
}

# Stages that may legitimately be PENDING while the script is approved.
LATE_STAGES = ("posting", "analytics")

# Course advice (Seefluencer course notebook), not platform data. Percent values are 0-100.
THRESHOLDS = {
    "watched_full_pct": 20.0,
    "avg_watch_pct": 50.0,
    "replicate_views": 100000,
    "source": "course",
}

HEADING = re.compile(r"^##\s+Viral Checklist\b", re.IGNORECASE)
NEXT_HEADING = re.compile(r"^##\s+(?!#)")
VERDICT = re.compile(r"^(PASS|FAIL|N/A|PENDING)\b\s*:?\s*(.*)$", re.IGNORECASE | re.DOTALL)


def _clean(cell):
    return cell.strip().strip("`*").strip()


def _norm_stage(cell):
    return re.sub(r"[\s_-]+", " ", _clean(cell).lower())


def _extract_blocks(text):
    lines = text.splitlines()
    blocks, current = [], None
    for line in lines:
        if HEADING.match(line):
            current = []
            blocks.append(current)
        elif current is not None and NEXT_HEADING.match(line):
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def _rows(block_lines):
    for line in block_lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        stage, item, verdict = cells[0], cells[1], "|".join(cells[2:])
        if set(stage.strip() + item.strip() + verdict.strip()) <= set("-: "):
            continue
        if _norm_stage(stage) == "stage" and _clean(item).lower() == "item":
            continue
        yield _norm_stage(stage), _clean(item).lower(), verdict.strip()


def problems_in(text):
    """Every problem in the checklist block of `text`, one string each. Empty list = OK."""
    blocks = _extract_blocks(text)
    if not blocks:
        return ["no '## Viral Checklist' block found"]
    if len(blocks) > 1:
        return [f"{len(blocks)} '## Viral Checklist' blocks found: one block only"]

    problems, seen = [], {}
    for stage, item, verdict in _rows(blocks[0]):
        label = f"{stage}/{item}"
        if stage not in ITEMS:
            problems.append(f"{label}: unknown stage")
            continue
        if item not in ITEMS[stage]:
            problems.append(f"{label}: unknown item")
            continue
        if (stage, item) in seen:
            problems.append(f"{label}: listed twice")
            continue
        seen[(stage, item)] = True
        m = VERDICT.match(verdict)
        if not verdict:
            problems.append(f"{label}: empty verdict")
        elif not m:
            problems.append(f"{label}: verdict must be PASS, FAIL: reason, N/A: reason or PENDING: reason (got '{verdict}')")
        else:
            kind, reason = m.group(1).upper(), m.group(2).strip()
            if kind == "FAIL":
                problems.append(f"{label}: {reason or 'verdict is FAIL (no reason given)'}")
            elif kind in ("N/A", "PENDING") and not reason:
                problems.append(f"{label}: {kind} needs a reason")
            elif kind == "PENDING" and stage not in LATE_STAGES:
                problems.append(f"{label}: PENDING is only allowed for posting and analytics")

    for stage in STAGES:
        present = [i for i in ITEMS[stage] if (stage, i) in seen]
        if not present and not any(s == stage for s, _ in seen):
            problems.append(f"{stage}: stage missing")
            continue
        for item in ITEMS[stage]:
            if (stage, item) not in seen:
                problems.append(f"{stage}/{item}: item missing")
    return problems


def check(path):
    """Return the list of problems for the av-script.md at `path` (raises OSError if unreadable)."""
    return problems_in(Path(path).read_text(encoding="utf-8"))


def _number(value):
    """float from a number or a string like '21%' / '100,001'; None when it is not a number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().rstrip("%").strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _pct(stats, pct_key, frac_key, notes, label):
    """A 0-100 percentage from `pct_key`, else from a 0-1 fraction under `frac_key`."""
    for key, scale, hi in ((pct_key, 1.0, 100.0), (frac_key, 100.0, 1.0)):
        if key in stats and stats[key] is not None:
            n = _number(stats[key])
            if n is None:
                notes.append(f"{label}: {key} is not a number")
            elif not 0 <= n <= hi:
                notes.append(f"{label}: {key}={stats[key]} is outside 0-{hi:g}")
            else:
                return n * scale
    notes.append(f"{label}: unknown, key {pct_key} (or {frac_key}) not present")
    return None


def rate(stats):
    """Verdict of one video's analytics against the course thresholds.

    Reads the keys tools/yt_stats.py writes: `avgViewPct` (percent, 0-100) and `views`.
    yt_stats does not write a watched-full figure (YouTube Studio only), so `watchedFullPct`
    (percent) or `watchedFull` (fraction) must be supplied by hand; absent = `unknown`.
    """
    stats = stats if isinstance(stats, dict) else {}
    notes = []
    wf = _pct(stats, "watchedFullPct", "watchedFull", notes, "watched_full")
    av = _pct(stats, "avgViewPct", "avgWatch", notes, "avg_watch")

    views = _number(stats.get("views"))
    if views is not None and views < 0:
        notes.append(f"replicate: views={stats.get('views')} is negative")
        views = None
    elif views is None:
        notes.append("replicate: unknown, key views not present or not a number")

    return {
        "watched_full": "unknown" if wf is None else ("pass" if wf >= THRESHOLDS["watched_full_pct"] else "fail"),
        "avg_watch": "unknown" if av is None else ("pass" if av >= THRESHOLDS["avg_watch_pct"] else "fail"),
        "replicate": "unknown" if views is None else ("yes" if views > THRESHOLDS["replicate_views"] else "no"),
        "notes": notes,
        "source": THRESHOLDS["source"],
    }


TIMELINE_ORDER = ("thumbnail", "hook", "foreshadow", "body", "cta")
TIMELINE_REQUIRED = ("hook", "foreshadow", "body", "cta")
# Stage -> latest end second (F13, notebook fd70ee32), before tolerance.
TIMELINE_END_MAX = {"hook": 3.0, "foreshadow": 6.0}
PROFILES = Path(__file__).resolve().parent.parent / "media" / "layout-profiles.json"
RANGE = re.compile(r"^(\d+(?:\.\d+)?)\s*[-\u2013]\s*(\d+(?:\.\d+)?)\s*s?$")


def timeline_tolerance():
    """`timeline_tolerance_s` of the short-organic profile (seconds)."""
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    return float(data["profiles"]["short-organic"]["timeline_tolerance_s"]["value"])


def _timeline_rows(text):
    """(rows, found_columns): rows are (tahap, detik) cells of the table with both columns."""
    rows, cols, found = [], None, False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            cols = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        low = [_clean(c).lower() for c in cells]
        if "tahap" in low and "detik" in low:
            cols, found = (low.index("tahap"), low.index("detik")), True
            continue
        if cols and len(cells) > max(cols):
            rows.append((_clean(cells[cols[0]]), _clean(cells[cols[1]])))
    return rows, found


def timeline_problems(text, tolerance=None):
    """Problems in the Tahap/Detik table of `text`; None when the table has no such columns."""
    rows, found = _timeline_rows(text)
    if not found:
        return None
    tol = timeline_tolerance() if tolerance is None else tolerance
    problems, spans = [], []
    for tahap, detik in rows:
        stage = tahap.lower()
        if stage not in TIMELINE_ORDER:
            problems.append(f"{tahap}: unknown stage (use Thumbnail, Hook, Foreshadow, Body, CTA)")
            continue
        m = RANGE.match(detik)
        if not m:
            problems.append(f"{tahap}: Detik '{detik}' is not a range like 0-3")
            continue
        a, b = float(m.group(1)), float(m.group(2))
        if b <= a:
            problems.append(f"{tahap}: Detik '{detik}' must end after it starts")
            continue
        spans.append((stage, a, b))
        limit = TIMELINE_END_MAX.get(stage)
        if limit is not None and b > limit + tol:
            problems.append(f"{tahap}: ends at {b:g} s, must end by {limit:g} s (+{tol:g} s tolerance)")
    present = [s for s, _, _ in spans]
    for stage in TIMELINE_REQUIRED:
        if stage not in present and not any(r[0].lower() == stage for r in rows):
            problems.append(f"{stage}: stage missing")
    idx = [TIMELINE_ORDER.index(s) for s in present]
    if idx != sorted(idx):
        problems.append("stages are out of order: expected Thumbnail, Hook, Foreshadow, Body, CTA")
    for (s1, _, b1), (s2, a2, _) in zip(spans, spans[1:]):
        if a2 + tol < b1 and idx == sorted(idx):
            problems.append(f"{s2}: starts at {a2:g} s before {s1} ends at {b1:g} s")
    return problems


def _cmd_timeline(path):
    try:
        found = timeline_problems(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as exc:
        print(f"viral_checklist: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    if found is None:
        print(f"viral_checklist: {path} has no table with Tahap and Detik columns", file=sys.stderr)
        return 2
    if found:
        for line in found:
            print(f"FAIL {line}")
        print(f"viral_checklist: {len(found)} timeline problem(s) in {path}")
        return 1
    print(f"viral_checklist: timeline OK {path}")
    return 0


def _cmd_check(path):
    try:
        found = check(path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"viral_checklist: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    if found:
        for line in found:
            print(f"FAIL {line}")
        print(f"viral_checklist: {len(found)} problem(s) in {path}")
        return 1
    print(f"viral_checklist: OK ({sum(len(v) for v in ITEMS.values())} items decided) {path}")
    return 0


def _cmd_rate(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"viral_checklist: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    videos = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(videos, list):
        print(f"viral_checklist: {path} has no 'videos' list", file=sys.stderr)
        return 2
    for video in videos:
        vid = video.get("videoId", "?") if isinstance(video, dict) else "?"
        print(f"{vid}: {json.dumps(rate(video), ensure_ascii=False)}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="viral_checklist", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="verify the Viral Checklist block of an av-script.md").add_argument("script")
    sub.add_parser("rate", help="verdict from packaging/calibration.json").add_argument("calibration")
    sub.add_parser("timeline", help="verify the Tahap/Detik table of an av-script.md (F13)").add_argument("script")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.cmd == "timeline":
        return _cmd_timeline(args.script)
    return _cmd_check(args.script) if args.cmd == "check" else _cmd_rate(args.calibration)


if __name__ == "__main__":
    sys.exit(main())
