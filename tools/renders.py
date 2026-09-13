#!/usr/bin/env python3
"""In-session render ledger for indusia-image-gen / indusia-video-gen renders.

    python3 tools/renders.py <project> --print

Every render a skill offers through the indusia MCP tools gets one entry in
`{project}/renders.json`, keyed by output file. The ledger lets a batch re-offer
be a no-op when the prompt hasn't changed since the last successful render, and
gives a durable place to keep the error text when a render fails instead of
silently forgetting it happened.
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
    """sha256 of a prompt, normalised so CRLF and trailing per-line whitespace don't
    change the hash — a prompt copy-pasted with different line endings should still
    be recognised as unchanged."""
    normalized_lines = [line.rstrip() for line in prompt.replace("\r\n", "\n").split("\n")]
    normalized = "\n".join(normalized_lines)
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

    Returns {"local_path", "cdn_url", "error"}. When no local path is found, `error`
    is set to the whole text (the MCP call likely failed) and both paths are None.
    """
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
    if duration_s not in (4, 6, 8):
        return False, f"duration {duration_s}s not in 4/6/8"
    if aspect not in ("16:9", "9:16"):
        return False, f"aspect {aspect} not supported"
    if mode in ("frame", "i2v") and len(refs) > 2:
        return False, f"too many refs for {mode}"
    if mode == "ingredients" and len(refs) > 3:
        return False, f"too many refs for {mode}"
    return True, ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--print", dest="do_print", action="store_true")
    args = ap.parse_args(argv)

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
