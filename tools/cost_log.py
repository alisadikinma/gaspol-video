#!/usr/bin/env python3
"""Cost log: units per billed render, money computed from media/pricing.json.

    python3 tools/cost_log.py <project> add --kind K --units N [--scene S] [--status ok|failed] [--note T]
    python3 tools/cost_log.py <project> report
    python3 tools/cost_log.py <project> estimate --plan <json file or inline json>
    python3 tools/cost_log.py <project> budget --set N
    python3 tools/cost_log.py <project> check

Entries store units, never money, so a corrected price fixes history. An item whose
price is null or whose source is empty is UNPRICED: its units are shown, money never.
Env GASPOL_PRICING overrides the pricing file path.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PRICING_DEFAULT = Path(__file__).resolve().parent.parent / "media" / "pricing.json"


def _pricing_path() -> Path:
    return Path(os.environ.get("GASPOL_PRICING") or PRICING_DEFAULT)


def load_pricing() -> dict:
    return json.loads(_pricing_path().read_text(encoding="utf-8"))


def _price_of(item: dict):
    """Price number, or None when UNPRICED (null price or empty source)."""
    if item.get("price") is None or not str(item.get("source", "")).strip():
        return None
    return item["price"]


def _log_path(project) -> Path:
    return Path(project) / "work" / "cost-log.json"


class CostLogError(Exception):
    """cost-log.json exists but is not the expected shape. The file is never rewritten."""


def load_log(project) -> dict:
    path = _log_path(project)
    if not path.exists():
        return {"budget": None, "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CostLogError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise CostLogError(f"{path}: expected an object with an 'entries' list")
    budget = data.get("budget")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float))):
        raise CostLogError(f"{path}: 'budget' must be a number or null")
    data.setdefault("budget", None)
    return data


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


def _cmd_add(args) -> int:
    kinds = sorted(load_pricing()["items"])
    if args.kind not in kinds:
        print(f"cost_log: unknown kind {args.kind!r}; known kinds: {', '.join(kinds)}",
              file=sys.stderr)
        return 2
    units = _parse_units(args.units)
    if units is None:
        print(f"cost_log: units must be a finite number >= 0, got {args.units!r}",
              file=sys.stderr)
        return 2
    args.units = units
    log = load_log(args.project)
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": args.kind,
        "units": args.units,
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
    log = load_log(args.project)
    pricing = load_pricing()
    items = pricing["items"]
    currency = pricing.get("currency", "")
    units: dict = {}
    failed_units = 0.0
    total_units = 0.0
    total_money = 0.0
    unpriced = []
    priced_any = False
    for e in log["entries"]:
        units[e["kind"]] = units.get(e["kind"], 0) + e["units"]
        total_units += e["units"]
        if e.get("status") == "failed":
            failed_units += e["units"]
    for kind, n in units.items():
        item = items.get(kind, {})
        price = _price_of(item)
        unit = item.get("unit", "unit")
        if price is None:
            print(f"{kind}: {_fmt(n)} {unit} UNPRICED")
            unpriced.append(kind)
        else:
            money = n * price
            total_money += money
            priced_any = True
            print(f"{kind}: {_fmt(n)} {unit} = {money:.2f} {currency}".rstrip())
    share = (failed_units / total_units * 100) if total_units else 0
    print(f"failed share: {share:.0f}%")
    if priced_any:
        note = f" (excludes UNPRICED: {', '.join(unpriced)})" if unpriced else ""
        print(f"total: {total_money:.2f} {currency}".rstrip() + note)
    else:
        print("total: n/a" + (f" (UNPRICED: {', '.join(unpriced)})" if unpriced else ""))
    if log["budget"] is not None:
        print(f"budget: {_fmt(log['budget'])} {currency}".rstrip())
    return 0


def _priced_total(log: dict, items: dict) -> float:
    total = 0.0
    for e in log["entries"]:
        price = _price_of(items.get(e["kind"], {}))
        if price is not None:
            total += e["units"] * price
    return total


def _parse_plan(text: str):
    """Plan dict kind -> units from a JSON file path or inline JSON; None when invalid."""
    try:
        raw = Path(text).read_text(encoding="utf-8") if Path(text).is_file() else text
        plan = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(plan, dict):
        return None
    out = {}
    for kind, n in plan.items():
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            return None
        units = _parse_units(str(n))
        if units is None:
            return None
        out[kind] = units
    return out


def _cmd_estimate(args) -> int:
    pricing = load_pricing()
    items = pricing["items"]
    plan = _parse_plan(args.plan)
    if plan is None:
        print("cost_log: --plan must be a JSON object (inline or file) of kind -> units >= 0",
              file=sys.stderr)
        return 2
    unknown = sorted(k for k in plan if k not in items)
    if unknown:
        print(f"cost_log: unknown kind(s) {', '.join(unknown)}; known kinds: "
              f"{', '.join(sorted(items))}", file=sys.stderr)
        return 2
    unpriced = sorted(k for k in plan if _price_of(items[k]) is None)
    if unpriced:
        print(f"cost_log: cannot estimate, UNPRICED item(s): {', '.join(unpriced)}. "
              f"Fill price and source in {_pricing_path()}", file=sys.stderr)
        return 2
    currency = pricing.get("currency", "")
    total = 0.0
    for kind, n in plan.items():
        money = n * _price_of(items[kind])
        total += money
        print(f"{kind}: {_fmt(n)} {items[kind].get('unit', 'unit')} = {money:.2f} {currency}".rstrip())
    print(f"estimate: {total:.2f} {currency}".rstrip())
    return 0


def _cmd_budget(args) -> int:
    value = _parse_units(args.set)
    if value is None:
        print(f"cost_log: budget must be a finite number >= 0, got {args.set!r}", file=sys.stderr)
        return 2
    log = load_log(args.project)
    log["budget"] = value
    save_log(args.project, log)
    print(f"budget set to {_fmt(value)}")
    return 0


def _cmd_check(args) -> int:
    log = load_log(args.project)
    if log["budget"] is None:
        print("no budget set")
        return 0
    total = _priced_total(log, load_pricing()["items"])
    if total > log["budget"]:
        print(f"over budget: {total:.2f} > {_fmt(log['budget'])}")
        return 1
    print(f"within budget: {total:.2f} <= {_fmt(log['budget'])}")
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
    p_est = sub.add_parser("estimate")
    p_est.add_argument("--plan", required=True)
    p_bud = sub.add_parser("budget")
    p_bud.add_argument("--set", required=True)
    sub.add_parser("check")
    args = ap.parse_args(argv)
    handlers = {"add": _cmd_add, "report": _cmd_report, "estimate": _cmd_estimate,
                "budget": _cmd_budget, "check": _cmd_check}
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
