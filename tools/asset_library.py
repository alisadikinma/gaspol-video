#!/usr/bin/env python3
"""Cross-project library for generic images, so a plain warehouse aisle is rendered once.

    python3 tools/asset_library.py find --prompt-file P --aspect 16:9
    python3 tools/asset_library.py add  --file F --prompt-file P --aspect 16:9 --model nano-banana-2 \
        --tags gudang,forklift --description "..." [--project DIR] [--force]
    python3 tools/asset_library.py list [--tag T]
    python3 tools/asset_library.py use  --id ID --to <project>/ref/<name>.png [--force]

Store: `asset_home.library("images")` (`${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/images`),
`catalog.json` plus `<id>.png`. The id is the first 16 hex of the prompt's sha256 (same
normalisation as the render ledger) + `-` + the aspect with `:` written `x`. `find` is exact:
same normalised prompt and same aspect, never fuzzy. Faces, logos, UI, products, costumes and
real locations are project-specific and `add` refuses them.

Exit codes: 0 ok, 1 `find` miss or other error, 2 refused by a guard.

Stdlib only.
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# tools/ is not a package on sys.path when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import asset_home  # noqa: E402
from tools.renders import prompt_sha256  # noqa: E402

ASPECTS = ("16:9", "9:16", "1:1", "4:3", "3:4")

# Project-specific by definition: cast/brand/ui/product/costume/env reference files, an identity
# lock, or a scene-NN- / scene-NNb- continuity ref. The prefix words must start a token so "environment"
# and "business" do not trip them.
_PROJECT_SPECIFIC = re.compile(
    r"(?<![A-Za-z0-9])(?:cast|brand|ui|product|costume|env)-|Maintain exact facial identity|scene-\d{2}[a-z]?-")
_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")


class LibraryError(Exception):
    pass


def _catalog_path():
    return asset_home.library("images") / "catalog.json"


def _load():
    try:
        return json.loads(_catalog_path().read_text()).get("images", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def _save(entries):
    path = _catalog_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"images": entries}, indent=2) + "\n")
    os.replace(tmp, path)


def make_id(prompt, aspect):
    return f"{prompt_sha256(prompt)[:16]}-{aspect.replace(':', 'x')}"


def _guard(file, prompt, aspect):
    match = _PROJECT_SPECIFIC.search(prompt)
    if match:
        raise LibraryError(
            f"prompt contains {match.group(0)!r}: faces, logos, UI, products, costumes and "
            "locations are project-specific and never library assets")
    if aspect not in ASPECTS:
        raise LibraryError(f"aspect {aspect!r} not supported (use one of {', '.join(ASPECTS)})")
    with open(file, "rb") as fh:
        head = fh.read(8)
    if not head.startswith(_MAGIC):
        raise LibraryError(f"{file} is not a PNG or JPEG file")


def add(file, prompt, aspect, model="", tags=(), description="", project=None, force=False):
    _guard(file, prompt, aspect)
    id_ = make_id(prompt, aspect)
    entries = _load()
    if not force and any(e.get("id") == id_ for e in entries):
        raise LibraryError(f"{id_} is already in the library (use --force to replace it)")
    dest = asset_home.library("images") / f"{id_}.png"
    shutil.copy2(file, dest)
    entries = [e for e in entries if e.get("id") != id_]
    entries.append({
        "id": id_,
        "file": dest.name,
        "prompt_sha256": prompt_sha256(prompt),
        "model": model,
        "aspect": aspect,
        "tags": list(tags),
        "description": description,
        "source_project": str(project) if project else "",
        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    _save(entries)
    return id_


def find(prompt, aspect):
    id_ = make_id(prompt, aspect)
    for entry in _load():
        if entry.get("id") == id_:
            path = asset_home.library("images") / entry["file"]
            return path if path.is_file() else None
    return None


def list_entries(tag=None):
    return [e for e in _load() if tag is None or tag in e.get("tags", [])]


def use(id_, to, force=False):
    entry = next((e for e in _load() if e.get("id") == id_), None)
    src = asset_home.library("images") / entry["file"] if entry else None
    if src is None or not src.is_file():
        raise LibraryError(f"no library image with id {id_!r}")
    to = Path(to)
    if to.exists() and not force:
        raise LibraryError(f"{to} already exists (use --force to overwrite)")
    to.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, to)
    return to


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="print the stored path for this exact prompt + aspect; exit 1 if absent")
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--aspect", required=True)

    p = sub.add_parser("add", help="store a rendered image (refused for project-specific prompts)")
    p.add_argument("--file", required=True)
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--aspect", required=True)
    p.add_argument("--model", default="")
    p.add_argument("--tags", default="", help="comma separated")
    p.add_argument("--description", default="")
    p.add_argument("--project", help="project folder the image came from")
    p.add_argument("--force", action="store_true", help="replace an existing entry")

    p = sub.add_parser("list", help="id, aspect, tags, description")
    p.add_argument("--tag")

    p = sub.add_parser("use", help="copy a library image into a project")
    p.add_argument("--id", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--force", action="store_true", help="overwrite an existing file")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "find":
            path = find(Path(args.prompt_file).read_text(), args.aspect)
            if path is None:
                return 1
            print(path)
        elif args.cmd == "add":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            id_ = add(args.file, Path(args.prompt_file).read_text(), args.aspect, args.model,
                      tags, args.description, args.project, args.force)
            print(f"added {id_}")
        elif args.cmd == "list":
            for e in list_entries(args.tag):
                print(f"{e['id']}\t{e['aspect']}\t{','.join(e.get('tags', []))}\t{e.get('description', '')}")
        else:
            print(f"copied to {use(args.id, args.to, args.force)}")
    except LibraryError as exc:
        print(f"asset_library: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"asset_library: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
