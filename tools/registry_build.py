#!/usr/bin/env python3
"""Tool registry: load, discover and validate `tools/registry.json`.

    python3 tools/registry_build.py validate [--coverage] [--root DIR]
    python3 tools/registry_build.py render [--check] [--root DIR]
    python3 tools/registry_build.py suggest [--top N] [--text-file PATH]
    python3 tools/registry_build.py hook < payload.json

`registry.json` is the single source of truth for every tool and every
task-to-tool route. `validate` exits 0 when it is sound, 1 listing every
problem (one per line, `<id or route #>: <problem>`) and 2 when the registry
file is missing or not JSON. `render` rewrites the routes table in
`docs/tool-routing.md` between two marker comments; `render --check` exits 1
when that block differs from the registry and writes nothing. `suggest` ranks
registered tools against a text (stdin or `--text-file`) and always exits 0.
`hook` is the PreToolUse reminder behind `hooks/tool-reminder.sh`: it never
blocks, and every failure is one `tool-reminder: <reason>` line on stderr. `--coverage` also demands that every file found
under `tools/` has an entry and is reachable from a route (or says why not).
"""

import argparse
import json
import os
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
FF_OWNERS = ("tools/vidkit/ff.py", "tools/vidkit/js/ff.mjs")
FFPROBE_RE = re.compile(r"\bffprobe\b")
WORD_RE = re.compile(r"[a-z0-9]+")
TOKEN_RE = re.compile(r"[a-z0-9-]+")
SCAN_LIMIT = 200 * 1024
HOOK_EXTS = {".py", ".mjs", ".sh"}
HOOK_SKIP_DIRS = ("tools", "tests", "templates")
HOOK_KEYWORDS = re.compile(r"ffmpeg|ffprobe|remotion", re.IGNORECASE)
HOOK_HEAD = "gaspol-video: tools that already do similar work:\n"
HOOK_RULE = (
    "Use one, or extend tools/vidkit with a test and a registry row (docs/tool-routing.md). "
    "If none fits, say why in your reply."
)
SCAN_GLOBS = ("tools/**/*.py", "tools/**/*.mjs")
GLOBS = ("tools/*.py", "tools/*.mjs", "tools/vidkit/*.py", "tools/vidkit/js/*.mjs")
# GV-25 new-tool gate. Two tools of one phase that share this share of the smaller task list need
# distinct_because on both, or a replaces link. A tool must be named by a test, and used by a
# skill, agent, reference, hook, template or another tool. docs/ and the registry do not count as
# use: vidkit smooth-track had a route and a docs row, and no caller.
OVERLAP_MAX = 0.5
TEST_GLOBS = ("tests/**/*.py", "tests/**/*.mjs", "tests/**/*.sh")
USE_GLOBS = ("skills/**/*.md", "agents/*.md", "reference/**/*.md", "hooks/*",
             "templates/**/*.mjs", "templates/**/*.ts", "templates/**/*.tsx")
CODE_GLOBS = ("tools/**/*.py", "tools/**/*.mjs", "tools/*.sh")


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
            ta, tb = set(a["tasks"]), set(b["tasks"])
            if a.get("phase") != b.get("phase") or not ta or not tb:
                continue
            share = len(ta & tb) / min(len(ta), len(tb))
            if share < OVERLAP_MAX:
                continue
            if a["id"] in b["replaces"] or b["id"] in a["replaces"]:
                continue
            if a.get("distinct_because") and b.get("distinct_because"):
                continue
            if ta == tb:
                problems.append(f"{b['id']}: duplicate of {a['id']}")
            else:
                problems.append(f"{b['id']}: overlaps {a['id']} on {share:.0%} of tasks "
                                "(add distinct_because or replaces)")


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
            # A pipe is escaped only after an odd run of backslashes; `\\|` is a bare pipe in GFM.
            elif re.search(r"(?<!\\)(?:\\\\)*\|", v) or "\n" in v:
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
                problems.append(f"{aid}: stale ffprobe_allow entry (no ffprobe in file)")
        if not isinstance(a.get("reason"), str) or not a["reason"].strip():
            problems.append(f"{aid}: ffprobe_allow reason is empty")


def _scan_ffprobe(reg, root, problems):
    allow = reg.get("ffprobe_allow", [])
    listed = {a["id"] for a in allow if isinstance(a, dict) and isinstance(a.get("id"), str)}
    for pattern in SCAN_GLOBS:
        for p in sorted(root.glob(pattern)):
            rel = p.relative_to(root).as_posix()
            if rel in FF_OWNERS or not p.is_file():
                continue
            try:
                hit = FFPROBE_RE.search(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if hit and rel not in listed:
                problems.append(f"{rel}: ffprobe outside vidkit/ff.py or vidkit/js/ff.mjs and not in ffprobe_allow")


def _texts(root, globs):
    out = {}
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = p.read_text(errors="ignore")
    return out


def _vidkit_commands(root):
    """{module stem: {cli commands}} read from the dispatch in tools/vidkit/__main__.py, so a skill
    that says `vidkit xfade` counts as using join.py."""
    main = root / "tools/vidkit/__main__.py"
    out = {}
    if not main.is_file():
        return out
    src = main.read_text(errors="ignore")
    for m in re.finditer(r'a\.cmd == "([\w-]+)":(.*?)(?=\n {8}(?:elif|else)\b|\Z)', src, re.S):
        for mod in set(re.findall(r"\b(\w+)\.\w+\(", m.group(2))):
            out.setdefault(mod, set()).add(m.group(1))
    return out


def _ref_patterns(tid, commands):
    """What counts as naming a tool: its file name, an import line, `vidkit.<stem>` /
    `tools.<stem>`, or a `vidkit <cmd>` that dispatches to it. A bare word does not: `track`
    appears all over the skills (`--mode track`) and let vidkit/track.py pass."""
    stem, name = Path(tid).stem, Path(tid).name
    e = re.escape(stem)
    pats = [r"(?<![\w-])" + re.escape(name) + r"\b",
            r"^\s*(?:from|import)\b[^\n]*\b" + e + r"\b",
            r"\b(?:vidkit|tools)\." + e + r"\b"]
    if tid.startswith("tools/vidkit/") and not tid.startswith("tools/vidkit/js/"):
        pats += [r"\bvidkit\s+" + re.escape(c) + r"\b" for c in sorted(commands.get(stem, ()))]
    return [re.compile(p, re.M) for p in pats]


def _check_tested_and_used(tools, root, problems):
    tests = _texts(root, TEST_GLOBS)
    use = _texts(root, USE_GLOBS)
    # __main__/__init__ import every module, so they would make every vidkit module "used".
    code = {rel: text for rel, text in _texts(root, CODE_GLOBS).items()
            if not rel.endswith(("/__main__.py", "/__init__.py")) and not rel.startswith("tools/registry")}
    commands = _vidkit_commands(root)
    for t in tools:
        if not isinstance(t, dict) or not isinstance(t.get("id"), str):
            continue
        tid = t["id"]
        pats = _ref_patterns(tid, commands)

        def named(texts, skip=None):
            return any(p.search(text) for rel, text in texts.items() if rel != skip for p in pats)

        if not named(tests):
            problems.append(f"{tid}: no test names it")
        reason = t.get("internal_reason")
        if isinstance(reason, str) and reason.strip():
            continue
        if not named(use) and not named(code, skip=tid):
            problems.append(f"{tid}: not used by any skill, reference or tool (add internal_reason)")


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
        _scan_ffprobe(reg, root, problems)
        for tid in discover(root):
            if tid not in ids_seen:
                problems.append(f"{tid}: not in registry")
        for t in tools:
            if not isinstance(t, dict) or t.get("id") not in ids_seen:
                continue
            reason = t.get("internal_reason")
            if t["id"] not in routed and not (isinstance(reason, str) and reason.strip()):
                problems.append(f"{t['id']}: no route and no internal_reason")
        _check_tested_and_used([t for t in tools if isinstance(t, dict) and t.get("id") in ids_seen],
                               root, problems)
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


def text_words(text) -> set:
    """Words of a text: hyphen-joined tokens plus each of their hyphen parts."""
    words = set()
    for tok in TOKEN_RE.findall(str(text).lower()):
        words.add(tok)
        words.update(p for p in tok.split("-") if p)
    return words


def _tag_score(tag, words, skip=frozenset()) -> int:
    """2 for the whole tag as a word; else 1 per hyphen part (>=4 letters, not already
    scored as a purpose word) found as a word, capped at 2."""
    if tag in words:
        return 2
    if "-" in tag:
        parts = [p for p in tag.split("-") if len(p) >= 4 and p not in skip]
        return min(2, sum(1 for p in parts if p in words))
    return 0


def score_tool(tool, words) -> int:
    tasks = [t for t in tool.get("tasks", []) if isinstance(t, str)]
    purpose = set(w for w in WORD_RE.findall(str(tool.get("purpose", "")).lower()) if len(w) >= 4)
    score = sum(_tag_score(t, words, purpose) for t in tasks)
    return score + sum(1 for w in purpose if w in words)


def suggest_tools(reg, text, top=3) -> list:
    words = text_words(text)
    scored = []
    for order, t in enumerate(reg.get("tools", [])):
        if isinstance(t, dict) and isinstance(t.get("id"), str):
            s = score_tool(t, words)
            if s > 0:
                scored.append((-s, order, t))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [t for _, _, t in scored[: max(top, 0)]]


def cmd_suggest(args) -> int:
    root = Path(args.root)
    try:
        text = Path(args.text_file).read_text(encoding="utf-8", errors="replace") if args.text_file else sys.stdin.read()
        reg = load(root / REGISTRY_REL)
    except (RegistryError, OSError) as e:
        print(f"suggest: {e}", file=sys.stderr)
        return 0
    for t in suggest_tools(reg, text, args.top):
        print(f"{t['id']} \u2014 {t.get('purpose', '')}")
    return 0


def _payload_text(payload):
    """Return (path, text) of a Write/Edit payload, or None when malformed."""
    if not isinstance(payload, dict):
        return None
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return None
    path = ti.get("file_path")
    text = ti.get("content") if "content" in ti else ti.get("new_string")
    if not isinstance(path, str) or not path or not isinstance(text, str):
        return None
    return path, text[:SCAN_LIMIT]


def should_fire(payload, plugin_root) -> bool:
    got = _payload_text(payload)
    if got is None:
        return False
    path, text = got
    if os.path.splitext(path)[1].lower() not in HOOK_EXTS:
        return False
    if not text or not HOOK_KEYWORDS.search(text):
        return False
    p = Path(path)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(Path(plugin_root).resolve())
        except ValueError:
            return True
        parts = rel.parts
    else:
        parts = p.parts
    return not any(d in parts[:-1] for d in HOOK_SKIP_DIRS)


def hook_output(payload, reg) -> str:
    got = _payload_text(payload)
    text = got[1] if got else ""
    lines = [f"{t['id']} \u2014 {t.get('purpose', '')}" for t in suggest_tools(reg, text, 3)]
    ctx = (HOOK_HEAD + "\n".join(lines) + "\n" if lines else "") + HOOK_RULE
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}},
        ensure_ascii=False,
    )


def cmd_hook(args) -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, OSError) as e:
        print(f"tool-reminder: bad payload on stdin: {e}", file=sys.stderr)
        return 0
    try:
        if not should_fire(payload, args.root):
            return 0
        reg = load(Path(args.root) / REGISTRY_REL)
        out = hook_output(payload, reg)
    except Exception as e:  # the hook must never block a write
        print(f"tool-reminder: {e}", file=sys.stderr)
        return 0
    print(out)
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
    g = sub.add_parser("suggest", help="rank registered tools against a text")
    g.add_argument("--top", type=int, default=3, help="how many tools to print (default 3)")
    g.add_argument("--text-file", help="read the text from this file (default: stdin)")
    g.set_defaults(func=cmd_suggest)
    h = sub.add_parser("hook", help="PreToolUse reminder: payload JSON on stdin, never blocks")
    h.set_defaults(func=cmd_hook)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
