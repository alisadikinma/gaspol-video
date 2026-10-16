#!/usr/bin/env python3
"""Tool registry: load, discover and validate `tools/registry.json`.

    python3 tools/registry_build.py validate [--coverage] [--root DIR]
    python3 tools/registry_build.py render [--check] [--root DIR]

`registry.json` is the single source of truth for every tool and every
task-to-tool route. `validate` exits 0 when it is sound, 1 listing every
problem (one per line, `<id or route #>: <problem>`) and 2 when the registry
file is missing or not JSON. `render` rewrites the routes table in
`docs/tool-routing.md` between two marker comments; `render --check` exits 1
when that block differs from the registry and writes nothing. `--coverage` also demands that every file found
under `tools/` has an entry and is reachable from a route (or says why not).
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_REL = "tools/registry.json"
VERSION = 1
PHASES = {"1", "2", "3", "4", "5", "6", "7", "shared"}
TASK_RE = re.compile(r"^[a-z0-9-]+$")
PURPOSE_MAX = 140
EXCLUDED = {"tools/_venv.py", "tools/vidkit/__main__.py"}
DOC_REL = "docs/tool-routing.md"
BEGIN_MARK = "<!-- registry:routes:begin -->"
END_MARK = "<!-- registry:routes:end -->"
GLOBS = ("tools/*.py", "tools/*.mjs", "tools/vidkit/*.py", "tools/vidkit/js/*.mjs")


class RegistryError(Exception):
    pass


def load(path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise RegistryError(f"cannot read registry {path}: {e.strerror or e}")
    try:
        reg = json.loads(text)
    except json.JSONDecodeError as e:
        raise RegistryError(f"registry {path} is not valid JSON: {e}")
    if not isinstance(reg, dict):
        raise RegistryError(f"registry {path} is not a JSON object")
    return reg


def discover(root) -> list:
    root = Path(root)
    found = set()
    for pattern in GLOBS:
        for p in root.glob(pattern):
            rel = p.relative_to(root).as_posix()
            if p.name == "__init__.py" or rel in EXCLUDED:
                continue
            found.add(rel)
    return sorted(found)


def _check_tool(t, n, root, ids_seen, problems):
    if not isinstance(t, dict):
        problems.append(f"tool #{n}: entry must be an object")
        return None
    tid = t.get("id")
    if not isinstance(tid, str) or not tid:
        problems.append(f"tool #{n}: id must be a non-empty string")
        return None
    if tid in ids_seen:
        problems.append(f"{tid}: duplicate id")
    elif not (root / tid).is_file():
        problems.append(f"{tid}: file does not exist")
    ids_seen.add(tid)

    purpose = t.get("purpose")
    if not isinstance(purpose, str):
        problems.append(f"{tid}: purpose must be a string")
    elif not purpose.strip():
        problems.append(f"{tid}: purpose is empty")
    else:
        if "\n" in purpose:
            problems.append(f"{tid}: purpose has a newline")
        if len(purpose) > PURPOSE_MAX:
            problems.append(f"{tid}: purpose longer than {PURPOSE_MAX}")

    tasks = t.get("tasks")
    if not isinstance(tasks, list):
        problems.append(f"{tid}: tasks must be a list")
    else:
        if not 1 <= len(tasks) <= 6:
            problems.append(f"{tid}: tasks must hold 1-6 tokens")
        seen = set()
        for tok in tasks:
            if not isinstance(tok, str) or not TASK_RE.match(tok):
                problems.append(f"{tid}: bad task token {tok!r}")
            elif tok in seen:
                problems.append(f"{tid}: duplicate task {tok!r}")
            else:
                seen.add(tok)

    phase = t.get("phase")
    if not isinstance(phase, str) or phase not in PHASES:
        problems.append(f"{tid}: bad phase {phase!r}")

    if not isinstance(t.get("replaces"), list):
        problems.append(f"{tid}: replaces must be a list")
    for key in ("distinct_because", "internal_reason"):
        if not isinstance(t.get(key), str):
            problems.append(f"{tid}: {key} must be a string")
    return tid


def _check_duplicates(tools, problems):
    clean = [
        t
        for t in tools
        if isinstance(t, dict)
        and isinstance(t.get("id"), str)
        and isinstance(t.get("tasks"), list)
        and all(isinstance(x, str) for x in t["tasks"])
        and isinstance(t.get("replaces"), list)
    ]
    for i, b in enumerate(clean):
        for a in clean[:i]:
            if a["id"] == b["id"]:
                continue
            if a.get("phase") != b.get("phase") or set(a["tasks"]) != set(b["tasks"]):
                continue
            if a["id"] in b["replaces"] or b["id"] in a["replaces"]:
                continue
            if a.get("distinct_because") and b.get("distinct_because"):
                continue
            problems.append(f"{b['id']}: duplicate of {a['id']}")


def _check_routes(routes, ids, problems):
    if not isinstance(routes, list):
        problems.append("registry: routes must be a list")
        return set()
    routed = set()
    for n, r in enumerate(routes, 1):
        label = f"route #{n}"
        if not isinstance(r, dict):
            problems.append(f"{label}: entry must be an object")
            continue
        for key in ("task", "use"):
            v = r.get(key)
            if not isinstance(v, str) or not v.strip():
                problems.append(f"{label}: {key} is empty")
            elif ("|" in (re.sub(r"`[^`\n]*`", "", v) if key == "use" else v)) or "\n" in v:
                problems.append(f"{label}: {key} has a pipe or newline")
        rt = r.get("tools")
        if not isinstance(rt, list):
            problems.append(f"{label}: tools must be a list")
            continue
        for tid in rt:
            if tid not in ids:
                problems.append(f"{label}: unknown tool {tid}")
            else:
                routed.add(tid)
    return routed


def _check_ffprobe_allow(allow, root, problems):
    if not isinstance(allow, list):
        problems.append("registry: ffprobe_allow must be a list")
        return
    for n, a in enumerate(allow, 1):
        if not isinstance(a, dict) or not isinstance(a.get("id"), str):
            problems.append(f"ffprobe_allow #{n}: entry needs a string id")
            continue
        aid = a["id"]
        path = root / aid
        if not path.is_file():
            problems.append(f"{aid}: file does not exist")
        else:
            try:
                has = re.search(r"\bffprobe\b", path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                has = None
            if not has:
                problems.append(f"{aid}: ffprobe_allow is stale (file no longer uses ffprobe)")
        if not isinstance(a.get("reason"), str) or not a["reason"].strip():
            problems.append(f"{aid}: ffprobe_allow reason is empty")


def validate(reg, root, coverage=False) -> list:
    root = Path(root)
    problems = []
    if reg.get("version") != VERSION:
        problems.append(f"registry: version must be {VERSION}")
    tools = reg.get("tools", [])
    if not isinstance(tools, list):
        problems.append("registry: tools must be a list")
        tools = []
    ids_seen = set()
    for n, t in enumerate(tools, 1):
        _check_tool(t, n, root, ids_seen, problems)
    for t in tools:
        if isinstance(t, dict) and isinstance(t.get("replaces"), list):
            for rid in t["replaces"]:
                if rid not in ids_seen:
                    problems.append(f"{t.get('id')}: replaces unknown id {rid}")
    _check_duplicates(tools, problems)
    routed = _check_routes(reg.get("routes", []), ids_seen, problems)
    _check_ffprobe_allow(reg.get("ffprobe_allow", []), root, problems)
    if coverage:
        for tid in discover(root):
            if tid not in ids_seen:
                problems.append(f"{tid}: not in registry")
        for t in tools:
            if not isinstance(t, dict) or t.get("id") not in ids_seen:
                continue
            reason = t.get("internal_reason")
            if t["id"] not in routed and not (isinstance(reason, str) and reason.strip()):
                problems.append(f"{t['id']}: no route and no internal_reason")
    return problems


def cmd_validate(args) -> int:
    root = Path(args.root)
    try:
        reg = load(root / REGISTRY_REL)
    except RegistryError as e:
        print(f"registry: {e}", file=sys.stderr)
        return 2
    problems = validate(reg, root, coverage=args.coverage)
    if not problems:
        print("registry: ok")
        return 0
    for p in problems:
        print(p)
    print(f"registry: {len(problems)} problem(s)")
    return 1


def render_block(routes) -> str:
    lines = ["| I want to... | Use |", "|---|---|"]
    lines += [f"| {r['task']} | {r['use']} |" for r in routes]
    return "\n".join(lines) + "\n"


def cmd_render(args) -> int:
    root = Path(args.root)
    try:
        reg = load(root / REGISTRY_REL)
    except RegistryError as e:
        print(f"registry: {e}", file=sys.stderr)
        return 2
    doc = root / DOC_REL
    try:
        with open(doc, encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as e:
        print(f"routing table: cannot read {doc}: {e.strerror or e}", file=sys.stderr)
        return 2
    b = text.find(BEGIN_MARK + "\n")
    e = text.find(END_MARK)
    if b < 0 or e < 0 or e < b:
        print(
            f"routing table: {DOC_REL} needs {BEGIN_MARK} then {END_MARK} "
            "(marker missing or out of order)",
            file=sys.stderr,
        )
        return 2
    problems = [p for p in validate(reg, root) if "route" in p]
    if problems:
        for p in problems:
            print(p)
        print(f"registry: {len(problems)} route problem(s), not rendering")
        return 1
    start = b + len(BEGIN_MARK) + 1
    new = text[:start] + render_block(reg.get("routes", [])) + text[e:]
    if new == text:
        print("routing table: unchanged")
        return 0
    if args.check:
        print("routing table: drift between registry and " + DOC_REL)
        return 1
    with open(doc, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print(f"routing table: {len(reg.get('routes', []))} routes written")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Tool registry loader and validator.")
    ap.add_argument("--root", default=str(PLUGIN_ROOT), help="plugin root (default: this plugin)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check tools/registry.json")
    v.add_argument("--coverage", action="store_true", help="every tool file must be registered and routed")
    v.set_defaults(func=cmd_validate)
    r = sub.add_parser("render", help="write the routes table into docs/tool-routing.md")
    r.add_argument("--check", action="store_true", help="exit 1 on drift, write nothing")
    r.set_defaults(func=cmd_render)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
