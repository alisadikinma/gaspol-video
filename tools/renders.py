#!/usr/bin/env python3
"""In-session render ledger for indusia-image-gen / indusia-video-gen renders.

    python3 tools/renders.py <project> --print
    python3 tools/renders.py <project> hash --prompt-file P
    python3 tools/renders.py <project> check --file F --prompt-file P
    python3 tools/renders.py <project> record --json '<entry json>'
    python3 tools/renders.py <project> eligible --json '<scene json>'

Every render a skill offers through the indusia MCP tools gets one entry in
`{project}/renders.json`, keyed by output file. The ledger lets a batch re-offer
be a no-op when the prompt hasn't changed since the last successful render, and
gives a durable place to keep the error text when a render fails instead of
silently forgetting it happened.

The subcommands are the CLI a skill actually calls (write the prompt to a temp file
first, then pass `--prompt-file`) — never Python function names, which a skill has no
way to invoke: `hash` prints the prompt's sha256; `check` prints `render` or
`up-to-date`; `record` validates and writes one ledger entry (`--json-file` for a
large entry); `eligible` prints `eligible` or `ineligible: <reason>` for a Phase 5
scene.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_NAME = "renders.json"

_LOCAL_PATH_RE = re.compile(r"(/[^\s]+\.(?:png|jpg|jpeg|mp4))", re.IGNORECASE)
_URL_RE = re.compile(r"(https://[^\s]+)")


class RenderLedgerError(Exception):
    """The render ledger file exists but cannot be read as the expected JSON shape."""


def _ledger_path(project) -> Path:
    return Path(project) / LEDGER_NAME


def prompt_sha256(prompt: str) -> str:
    """sha256 of a prompt, normalised so CRLF, trailing per-line whitespace, and a
    single trailing newline don't change the hash — a prompt copy-pasted with
    different line endings, or written to a file with an editor's final newline,
    should still be recognised as unchanged ("a\\nb" == "a\\nb\\n")."""
    normalized_lines = [line.rstrip() for line in prompt.replace("\r\n", "\n").split("\n")]
    normalized = "\n".join(normalized_lines)
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load(project) -> dict:
    path = _ledger_path(project)
    if not path.exists():
        return {"renders": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RenderLedgerError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("renders"), list):
        raise RenderLedgerError(f"{path}: expected an object with a 'renders' list")
    return data


def needs_render(ledger: dict, file: str, prompt: str) -> bool:
    """False only when an entry for `file` is status 'done' with the same prompt hash."""
    target_hash = prompt_sha256(prompt)
    for entry in ledger.get("renders", []):
        if entry.get("file") == file:
            return not (entry.get("status") == "done" and entry.get("prompt_sha256") == target_hash)
    return True


def record(project, entry: dict) -> None:
    """Replace an existing entry with the same `file`, else append. Written atomically."""
    ledger = load(project)
    entry = dict(entry)
    if not entry.get("rendered_at"):
        entry["rendered_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    renders_list = ledger["renders"]
    for i, existing in enumerate(renders_list):
        if existing.get("file") == entry.get("file"):
            renders_list[i] = entry
            break
    else:
        renders_list.append(entry)

    path = _ledger_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_mcp_result(text: str) -> dict:
    """Extract a local artifact path and CDN URL from an indusia MCP summary string.

    The real shape (docs/evals/indusia-render-probe.md) is explicit `local: <path>` /
    `cdn_url: <url>` lines — parsed FIRST so a path with spaces, or an extension the
    old regex didn't know (`.webp`, `.mov`, ...), still comes through whole. Only when
    no `local:` line is present does this fall back to the old regex scan, which keeps
    the illustrative "Saved: .../URL: ..." shape working too.

    Returns {"local_path", "cdn_url", "error"}. When no local path is found either
    way, `error` is set to the whole text (the MCP call likely failed) and both paths
    are None.
    """
    local_path, cdn_url = None, None
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("local:"):
            local_path = stripped.split(":", 1)[1].strip()
        elif lower.startswith("cdn_url:"):
            cdn_url = stripped.split(":", 1)[1].strip()
    if local_path is not None:
        return {"local_path": local_path, "cdn_url": cdn_url or None, "error": None}

    local_match = _LOCAL_PATH_RE.search(text)
    url_match = _URL_RE.search(text)
    if local_match is None:
        return {"local_path": None, "cdn_url": None, "error": text}
    return {
        "local_path": local_match.group(1),
        "cdn_url": url_match.group(1) if url_match else None,
        "error": None,
    }


def video_render_eligibility(scene: dict) -> tuple[bool, str]:
    """Whether a Phase 5 scene can be rendered through indusia-video-gen (veo-3.1-fast).

    Input keys: `platform` (veo|seedance|kling), `mode` (frame|ingredients|i2v|extend),
    `duration_s` (number), `aspect` (16:9|9:16|...), `refs` (list). Rules are checked in
    order; the first failing rule's reason is returned. `(True, "")` when every rule
    passes.
    """
    platform = scene.get("platform")
    mode = scene.get("mode")
    duration_s = scene.get("duration_s")
    aspect = scene.get("aspect")
    refs = scene.get("refs") or []

    if platform != "veo":
        return False, f"platform {platform} is prompt-only; render it in its own UI"
    if mode == "extend":
        return False, "Scene Extension is not available in indusia-video-gen"
    try:
        duration_val = float(duration_s)
    except (TypeError, ValueError):
        return False, f"duration {duration_s!r} is not a number"
    if duration_val not in (4.0, 6.0, 8.0):
        return False, f"duration {duration_s}s not in 4/6/8"
    if aspect not in ("16:9", "9:16"):
        return False, f"aspect {aspect} not supported"
    if mode in ("frame", "i2v") and len(refs) > 2:
        return False, f"too many refs for {mode}"
    if mode == "ingredients" and len(refs) > 3:
        return False, f"too many refs for {mode}"
    return True, ""


_RENDER_PHASES = {"4A", "4B", "5"}
_RENDER_STATUSES = {"done", "failed", "skipped"}


def _load_json_arg(inline, file_path, kind):
    """Read a JSON object from `--json` (inline string) or `--json-file`. Exactly one
    is expected; neither given is a usage error, printed and signalled by returning
    None so the caller can exit 1."""
    if file_path:
        return json.loads(Path(file_path).read_text())
    if inline:
        return json.loads(inline)
    print(f"renders: {kind} needs --json or --json-file", file=sys.stderr)
    return None


def _cmd_hash(args):
    prompt = Path(args.prompt_file).read_text()
    print(prompt_sha256(prompt))
    return 0


def _cmd_check(args):
    try:
        ledger = load(args.project)
    except RenderLedgerError as exc:
        print(f"renders: {exc}", file=sys.stderr)
        return 1
    prompt = Path(args.prompt_file).read_text()
    print("render" if needs_render(ledger, args.file, prompt) else "up-to-date")
    return 0


def _cmd_record(args):
    entry = _load_json_arg(args.json, args.json_file, "record")
    if entry is None:
        return 1

    missing = [k for k in ("file", "phase", "status") if not entry.get(k)]
    if missing:
        print(f"renders: record entry missing required field(s): {', '.join(missing)}",
              file=sys.stderr)
        return 1
    if entry["phase"] not in _RENDER_PHASES:
        print(f"renders: record entry has invalid phase {entry['phase']!r} "
              f"(expected one of {sorted(_RENDER_PHASES)})", file=sys.stderr)
        return 1
    if entry["status"] not in _RENDER_STATUSES:
        print(f"renders: record entry has invalid status {entry['status']!r} "
              f"(expected one of {sorted(_RENDER_STATUSES)})", file=sys.stderr)
        return 1

    if args.prompt_file:
        entry["prompt_sha256"] = prompt_sha256(Path(args.prompt_file).read_text())
    if entry.get("cdn_url"):
        entry["cdn_url"] = entry["cdn_url"].split("?", 1)[0]

    record(args.project, entry)
    print(f"recorded {entry['file']} ({entry['status']})")
    return 0


def _cmd_eligible(args):
    scene = _load_json_arg(args.json, args.json_file, "eligible")
    if scene is None:
        return 1
    ok, reason = video_render_eligibility(scene)
    print("eligible" if ok else f"ineligible: {reason}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--print", dest="do_print", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p_hash = sub.add_parser("hash", help="print the prompt's normalised sha256")
    p_hash.add_argument("--prompt-file", required=True)

    p_check = sub.add_parser("check", help="'render' or 'up-to-date' for file+prompt")
    p_check.add_argument("--file", required=True)
    p_check.add_argument("--prompt-file", required=True)

    p_record = sub.add_parser("record", help="write one ledger entry")
    p_record.add_argument("--json")
    p_record.add_argument("--json-file")
    p_record.add_argument("--prompt-file", help="compute prompt_sha256 from this file")

    p_eligible = sub.add_parser("eligible", help="'eligible' or 'ineligible: <reason>'")
    p_eligible.add_argument("--json")
    p_eligible.add_argument("--json-file")

    args = ap.parse_args(argv)

    if args.cmd == "hash":
        return _cmd_hash(args)
    if args.cmd == "check":
        return _cmd_check(args)
    if args.cmd == "record":
        return _cmd_record(args)
    if args.cmd == "eligible":
        return _cmd_eligible(args)

    try:
        ledger = load(args.project)
    except RenderLedgerError as exc:
        print(f"renders: {exc}", file=sys.stderr)
        return 1

    if args.do_print:
        counts: dict[str, int] = {}
        for entry in ledger["renders"]:
            status = entry.get("status", "?")
            counts[status] = counts.get(status, 0) + 1
            print(f"{status:<8} {entry.get('phase', '?'):<4} {entry.get('file', '?')}  {entry.get('model', '?')}")
        for status, count in counts.items():
            print(f"{status}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
