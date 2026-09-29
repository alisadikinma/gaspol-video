#!/usr/bin/env python3
"""Where the reusable asset libraries live, and how they survive a plugin update.

    python3 tools/asset_home.py where
    python3 tools/asset_home.py adopt [--kind sfx|music|images]

Generated SFX clips and music tracks used to be written inside the plugin's own
`media/<kind>/library/`, which is a versioned cache directory: an update starts a fresh
version dir and every clip would be regenerated and re-billed. The libraries now live in
`${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/<kind>` (the same home the venv uses), and the
recipes (`palette.json`) stay in the plugin. `adopt` copies what earlier plugin versions
generated into the home library. It copies, never moves.

Stdlib only.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

KINDS = ("sfx", "music", "images")

# kind -> (catalog list key, media subfolder). Images have no adoption source in the plugin.
_LAYOUT = {"sfx": ("clips", "clips"), "music": ("tracks", "tracks")}

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def home():
    return Path(os.environ.get("GASPOL_VIDEO_HOME") or "~/.gaspol-video").expanduser()


def _check(kind):
    if kind not in KINDS:
        raise ValueError(f"unknown library kind {kind!r} (use one of {', '.join(KINDS)})")


def library(kind):
    _check(kind)
    path = home() / "library" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def recipes(kind):
    """The plugin's palette.json for this kind. Recipes ship with the plugin; outputs go home."""
    _check(kind)
    return PLUGIN_ROOT / "media" / kind / "library" / "palette.json"


def default_sources(kind):
    """Every place an earlier plugin version may have left generated files: each cached
    version dir plus the plugin's own media folder."""
    cache = Path("~/.claude/plugins/cache").expanduser()
    found = sorted(cache.glob(f"*/gaspol-video/*/media/{kind}/library")) if cache.is_dir() else []
    own = PLUGIN_ROOT / "media" / kind / "library"
    if own not in found:
        found.append(own)
    return found


def _read_catalog(path, key):
    try:
        return json.loads(path.read_text()).get(key, [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def adopt(kind, sources=None, log=print):
    """Copy (never move) clips/tracks from earlier plugin versions into the home library.

    Runs only while the home catalog is missing or empty. On an id collision the file with
    the newest mtime wins. `sources` are library dirs (each holding catalog.json); None means
    the real plugin cache. Returns the number of files copied.
    """
    _check(kind)
    if kind not in _LAYOUT:
        return 0
    key, _sub = _LAYOUT[kind]
    dest = library(kind)
    if _read_catalog(dest / "catalog.json", key):
        return 0

    chosen = {}
    for src in (default_sources(kind) if sources is None else sources):
        src = Path(src)
        for entry in _read_catalog(src / "catalog.json", key):
            file = src / entry.get("file", "")
            if not entry.get("id") or not file.is_file():
                continue
            mtime = file.stat().st_mtime
            best = chosen.get(entry["id"])
            if best is None or mtime > best[0]:
                chosen[entry["id"]] = (mtime, entry, file, src)

    if not chosen:
        return 0

    per_source = {}
    entries = []
    for id_ in sorted(chosen):
        _mtime, entry, file, src = chosen[id_]
        target = dest / entry["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        entries.append(entry)
        per_source[src] = per_source.get(src, 0) + 1
    (dest / "catalog.json").write_text(json.dumps({key: entries}, indent=2) + "\n")
    for src, count in per_source.items():
        log(f"adopted {count} {kind} file(s) from {src}")
    return len(entries)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where", help="print the library dirs")
    p = sub.add_parser("adopt", help="copy earlier plugin versions' clips/tracks into the home library")
    p.add_argument("--kind", choices=KINDS, help="default: sfx and music")
    args = ap.parse_args(argv)

    if args.cmd == "where":
        for kind in KINDS:
            print(f"{kind}: {library(kind)}")
        return 0
    total = 0
    for kind in ([args.kind] if args.kind else ["sfx", "music"]):
        total += adopt(kind)
    print(f"adopted {total} file(s) in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
