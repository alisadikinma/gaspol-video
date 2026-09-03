#!/usr/bin/env python3
"""Grow the shared SFX library from palette.json recipes.

    python3 tools/gen_sfx.py [--library DIR] [--only id1,id2] [--force] [--dry-run] [--renorm]

The library is the durable asset; each video is one draw from it. Recipes are written to be
GENERIC on purpose (`whoosh-soft`, not `whoosh-for-the-pelindo-video`) so the next project
reuses them, and every clip is normalised to the same loudness so a plan's gain_db means the
same thing from one clip to the next.

`--renorm` re-balances existing clips without calling the API at all, which is the cheap fix
when the target changes.

Stdlib only. Missing key or missing ffmpeg degrades loudly and lists what could not be made.
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
API_URL = "https://api.elevenlabs.io/v1/sound-generation"
MODEL = "eleven_text_to_sound_v2"

# Every clip lands here so a per-cue gain_db is perceptually meaningful across the library.
# Transients hit the peak ceiling before reaching the loudness target, which is why their
# plan gains sit 3-5 dB higher than the table suggests. See 14-sfx-design.md.
TARGET_LUFS = -20.0
TARGET_PEAK_DBFS = -1.5

DEFAULT_LIBRARY = Path("media/sfx/library")


class LibraryError(Exception):
    """The library or a recipe cannot be used as written."""


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise LibraryError(f"{Path(path).name} is not valid JSON: {exc.msg}") from exc


def load_palette(library):
    data = _read_json(Path(library) / "palette.json", {"recipes": []})
    return data.get("recipes", [])


def load_catalog(library):
    return _read_json(Path(library) / "catalog.json", {"clips": []})


def missing_recipes(library, only=None, force=False):
    """Which recipes still need a clip. Library-first: an existing clip is never regenerated."""
    recipes = load_palette(library)
    by_id = {r["id"]: r for r in recipes}

    if only:
        unknown = [i for i in only if i not in by_id]
        if unknown:
            raise LibraryError(
                f"palette.json has no recipe for: {', '.join(unknown)}. "
                "Add the recipe first — generating without one leaves a clip nothing can reuse."
            )
        recipes = [by_id[i] for i in only]

    if force:
        return recipes

    have = {c["id"] for c in load_catalog(library).get("clips", [])}
    return [r for r in recipes if r["id"] not in have]


def loudnorm_args():
    return f"loudnorm=I={TARGET_LUFS}:TP={TARGET_PEAK_DBFS}:LRA=7"


def normalise(src, dest):
    if FFMPEG is None:
        raise LibraryError("ffmpeg not available to normalise the clip")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", str(src), "-af", loudnorm_args(),
         "-c:a", "libmp3lame", "-q:a", "2", str(dest)],
        check=True, capture_output=True,
    )
    return dest


def catalog_entry(recipe, file, loudness_lufs, peak_dbfs):
    """Provenance is part of the entry: a clip whose origin is unknown cannot be relicensed."""
    return {
        "id": recipe["id"],
        "file": file,
        "category": recipe.get("category", "uncategorised"),
        "tags": recipe.get("tags", []),
        "duration_s": recipe.get("duration_s"),
        "peak_dbfs": peak_dbfs,
        "loudness_lufs": loudness_lufs,
        "source": "elevenlabs-sfx",
        "model": MODEL,
        "license": "generated for this account; check the provider's terms before redistributing",
        "prompt": recipe.get("prompt", ""),
        "used_in": [],
    }


def _request_sfx(prompt, duration_s, api_key):
    body = json.dumps({
        "text": prompt,
        "duration_seconds": duration_s,
        "prompt_influence": 0.4,
        "model_id": MODEL,
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def generate(library, env=None, only=None, force=False, dry_run=False, log=print):
    library = Path(library)
    env = env if env is not None else {}
    clips_dir = library / "clips"

    recipes = missing_recipes(library, only=only, force=force)
    if not recipes:
        log("library is complete — nothing to generate")
        return {"degraded": False, "written": [], "pending": []}

    api_key = env.get("ELEVENLABS_API_KEY")
    if not api_key:
        reason = (
            "ELEVENLABS_API_KEY not set — no sound was generated. "
            "Set it in this plugin's .env, or source these from a royalty-free library and "
            "add them to catalog.json by hand with their real source and licence."
        )
        log(reason)
        for r in recipes:
            log(f"  pending: {r['id']} — \"{r['prompt']}\" ({r.get('duration_s')}s)")
        return {"degraded": True, "reason": reason, "written": [],
                "pending": [r["id"] for r in recipes]}

    if dry_run:
        for r in recipes:
            log(f"  would generate {r['id']} — \"{r['prompt']}\" ({r.get('duration_s')}s)")
        return {"degraded": False, "written": [], "pending": [r["id"] for r in recipes]}

    clips_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(library)
    written = []
    failed = []

    for recipe in recipes:
        try:
            raw = _request_sfx(recipe["prompt"], recipe.get("duration_s", 2.0), api_key)
        except urllib.error.HTTPError as exc:
            failed.append(f"{recipe['id']}: HTTP {exc.code}")
            log(f"  ! {recipe['id']}: HTTP {exc.code}")
            continue
        except OSError as exc:
            failed.append(f"{recipe['id']}: {exc}")
            log(f"  ! {recipe['id']}: {exc}")
            continue

        staging = clips_dir / f"{recipe['id']}.raw.mp3"
        staging.write_bytes(raw)
        final = clips_dir / f"{recipe['id']}.mp3"
        normalise(staging, final)
        staging.unlink(missing_ok=True)

        catalog["clips"] = [c for c in catalog.get("clips", []) if c["id"] != recipe["id"]]
        catalog["clips"].append(catalog_entry(
            recipe, f"clips/{final.name}", TARGET_LUFS, TARGET_PEAK_DBFS))
        written.append(recipe["id"])
        log(f"  {recipe['id']} -> clips/{final.name}")

    catalog["clips"].sort(key=lambda c: c["id"])
    (library / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    return {"degraded": False, "written": written, "pending": failed}


def renormalise(library, log=print):
    """Re-balance existing clips to the current target. No API call, no billing."""
    library = Path(library)
    catalog = load_catalog(library)
    for clip in catalog.get("clips", []):
        path = library / clip["file"]
        if not path.exists():
            log(f"  ! {clip['id']}: file missing at {clip['file']}")
            continue
        tmp = path.with_suffix(".renorm.mp3")
        normalise(path, tmp)
        tmp.replace(path)
        clip["loudness_lufs"] = TARGET_LUFS
        clip["peak_dbfs"] = TARGET_PEAK_DBFS
        log(f"  {clip['id']}: renormalised")
    (library / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", default=str(DEFAULT_LIBRARY))
    ap.add_argument("--only", help="comma-separated recipe ids")
    ap.add_argument("--force", action="store_true", help="regenerate even if a clip exists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--renorm", action="store_true", help="re-balance existing clips, no API call")
    args = ap.parse_args(argv)

    import os
    env = dict(os.environ)
    try:
        for line in Path(".env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip():
                    env.setdefault(k.strip(), v.strip())
    except OSError:
        pass

    try:
        if args.renorm:
            renormalise(args.library)
            return 0
        generate(args.library, env=env,
                 only=args.only.split(",") if args.only else None,
                 force=args.force, dry_run=args.dry_run)
        return 0
    except LibraryError as exc:
        print(f"gen_sfx: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
