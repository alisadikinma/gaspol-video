#!/usr/bin/env python3
"""Cost log: units of billed renders, failed attempts, re-rolls per scene. No prices.

    python3 tools/cost_log.py <project> add --kind K --units N [--scene S] [--status ok|failed] [--note T]
    python3 tools/cost_log.py <project> report

Storage: `{project}/work/cost-log.json` = {"entries": [{"ts","kind","scene"?,"units",
"status","note"?}]}. A `budget` key left by an older version is ignored on read and
dropped on the next write.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

KINDS = {
    "nb2-image": "image",
    "veo-3.1-fast-clip": "second",
    "eleven-tts": "1k-chars",
    "eleven-music": "second",
    "eleven-sfx": "clip",
}


class CostLogError(Exception):
    """cost-log.json exists but is not the expected shape. The file is never rewritten."""


def _log_path(project) -> Path:
    return Path(project) / "work" / "cost-log.json"


def load_log(project) -> dict:
    path = _log_path(project)
    if not path.exists():
        return {"entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CostLogError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise CostLogError(f"{path}: expected an object with an 'entries' list")
    return {"entries": data["entries"]}


def save_log(project, log: dict) -> None:
    path = _log_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _parse_units(text: str):
    try:
        n = float(text)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n >= 0 else None


def _pct(part: float, whole: float) -> str:
    return f"{(part / whole * 100) if whole else 0:.0f}%"


def _cmd_add(args) -> int:
    if args.kind not in KINDS:
        print(f"cost_log: unknown kind {args.kind!r}; known kinds: {', '.join(sorted(KINDS))}",
              file=sys.stderr)
        return 2
    units = _parse_units(args.units)
    if units is None:
        print(f"cost_log: units must be a finite number >= 0, got {args.units!r}",
              file=sys.stderr)
        return 2
    log = load_log(args.project)
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
        "units": units,
        "status": args.status,
    }
    if args.scene:
        entry["scene"] = args.scene
    if args.note:
        entry["note"] = args.note
    log["entries"].append(entry)
    save_log(args.project, log)
    print(f"logged {args.kind} {_fmt(units)} ({args.status})")
    return 0


def _cmd_report(args) -> int:
    entries = load_log(args.project)["entries"]
    per_kind: dict = {}
    rerolls: dict = {}
    total = failed = 0.0
    for e in entries:
        n = e["units"]
        row = per_kind.setdefault(e["kind"], [0.0, 0.0])
        row[0] += n
        total += n
        if e.get("status") == "failed":
            row[1] += n
            failed += n
            if e.get("scene"):
                rerolls[e["scene"]] = rerolls.get(e["scene"], 0) + 1
    for kind, (units, bad) in per_kind.items():
        print(f"{kind}: {_fmt(units)} {KINDS.get(kind, 'unit')}, failed {_pct(bad, units)}")
    print(f"entries: {len(entries)}")
    print(f"failed share: {_pct(failed, total)}")
    for scene, count in sorted(rerolls.items()):
        print(f"re-rolls scene {scene}: {count}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("--kind", required=True)
    p_add.add_argument("--units", required=True)
    p_add.add_argument("--scene")
    p_add.add_argument("--status", choices=["ok", "failed"], default="ok")
    p_add.add_argument("--note")
    sub.add_parser("report")
    args = ap.parse_args(argv)
    handlers = {"add": _cmd_add, "report": _cmd_report}
    try:
        return handlers[args.cmd](args)
    except CostLogError as exc:
        print(f"cost_log: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cost_log: write failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
