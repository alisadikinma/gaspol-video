#!/usr/bin/env python3
"""Grow the shared music-bed library from palette.json mood recipes.

    python3 tools/gen_music.py [--library media/music/library] [--only id1,id2]
                                [--length-s N] [--force] [--dry-run] [--renorm]

LIBRARY-FIRST: a mood whose tracks/<id>.mp3 already exists is skipped and never re-billed,
unless --force. Tracks are generated with ElevenLabs Music (force_instrumental) and
loudness-normalised toward the palette's target LUFS, clamped so the peak never crosses the
ceiling — the same shape as tools/gen_sfx.py, one octave down (minutes, not seconds).

`--renorm` re-balances existing tracks to the current target without calling the API.

Stdlib only. Missing key or missing ffmpeg degrades loudly and names what could not be made.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
API_URL = "https://api.elevenlabs.io/v1/music"

DEFAULT_LIBRARY = Path("media/music/library")

FALLBACK_DEFAULTS = {
    "model": "music_v2",
    "force_instrumental": True,
    "target_lufs": -20.0,
    "ceiling_dbfs": -1.5,
    "output_format": "mp3_44100_128",
}


class MusicLibraryError(Exception):
    """The music library or a mood recipe cannot be used as written."""


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise MusicLibraryError(f"{Path(path).name} is not valid JSON: {exc.msg}") from exc


def load_palette(library):
    path = Path(library) / "palette.json"
    if not path.exists():
        raise MusicLibraryError(
            f"palette not found: {path} — run from the plugin root or pass --library"
        )
    return _read_json(path, {"moods": []})


def load_defaults(palette):
    return {**FALLBACK_DEFAULTS, **palette.get("defaults", {})}


def load_catalog(library):
    return _read_json(Path(library) / "catalog.json", {"tracks": []})


def plan_work(palette, library, only=None, force=False):
    """Which moods still need a track. Library-first: an existing track is never regenerated
    unless force=True. Returns (todo, skipped) — todo is a list of mood dicts."""
    library = Path(library)
    moods = palette.get("moods", [])
    by_id = {m["id"]: m for m in moods}

    if only:
        unknown = [i for i in only if i not in by_id]
        if unknown:
            raise MusicLibraryError(f"unknown mood: {', '.join(unknown)}")
        moods = [by_id[i] for i in only]

    todo, skipped = [], []
    for mood in moods:
        track_path = library / "tracks" / f"{mood['id']}.mp3"
        if track_path.exists() and not force:
            skipped.append(mood["id"])
            continue
        todo.append(mood)
    return todo, skipped


def build_request(mood, defaults, length_s=None):
    """Pure request shape — no API key here, so it is testable without one. The caller adds
    xi-api-key at request time."""
    length_ms = int(round((length_s if length_s is not None else mood.get("duration_s", 60)) * 1000))
    body = {
        "prompt": mood["prompt"],
        "music_length_ms": length_ms,
        "model_id": defaults.get("model", "music_v2"),
        "force_instrumental": bool(defaults.get("force_instrumental", True)),
    }
    output_format = defaults.get("output_format", "mp3_44100_128")
    url = f"{API_URL}?output_format={output_format}"
    headers = {"Content-Type": "application/json", "Accept": "audio/mpeg"}
    return url, headers, json.dumps(body).encode("utf-8")


def _request_music(url, headers, body, api_key, timeout=300):
    req = urllib.request.Request(
        url, data=body, headers={**headers, "xi-api-key": api_key}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def gain_for(lufs, peak, target, ceiling):
    """dB to apply so the track sits at target LUFS, clamped so the peak never crosses the
    ceiling. A track with no measurable loudness (near-silent / gated to nothing) falls back
    to filling the ceiling from its peak instead."""
    if lufs is None or lufs < -50:
        return round(ceiling - peak, 2)
    gain = target - lufs
    if peak + gain > ceiling:
        gain = ceiling - peak
    return round(gain, 2)


def _run_capture(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout


def probe_duration(path):
    if FFPROBE is None:
        return None
    out = _run_capture([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)]).strip()
    try:
        return round(float(out), 3)
    except ValueError:
        return None


def measure_peak_dbfs(path):
    if FFMPEG is None:
        return None
    out = _run_capture([FFMPEG, "-hide_banner", "-i", str(path), "-af", "volumedetect",
                        "-f", "null", os.devnull])
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", out)
    return float(m.group(1)) if m else None


def measure_lufs(path):
    if FFMPEG is None:
        return None
    out = _run_capture([FFMPEG, "-hide_banner", "-i", str(path), "-af", "ebur128",
                        "-f", "null", os.devnull])
    matches = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", out)
    try:
        return float(matches[-1]) if matches else None
    except ValueError:
        return None


def apply_gain(path, gain_db):
    """Re-encode path with a volume shift, in place. A near-zero gain is a no-op."""
    if abs(gain_db) < 0.05:
        return
    path = Path(path)
    tmp = path.with_suffix(".norm.mp3")
    _run_capture([FFMPEG, "-y", "-hide_banner", "-i", str(path), "-af", f"volume={gain_db:.2f}dB",
                 "-c:a", "libmp3lame", "-q:a", "2", str(tmp)])
    if tmp.exists() and tmp.stat().st_size > 0:
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _measure_and_normalise(mood, path, defaults, log=print):
    """Normalise toward the target and return the measured (lufs, peak, duration) after."""
    if FFMPEG is None:
        log(f"  ! ffmpeg not available — normalisation skipped for {mood['id']}")
        return None, None, probe_duration(path)

    target_lufs = defaults.get("target_lufs", -20.0)
    ceiling_dbfs = defaults.get("ceiling_dbfs", -1.5)
    peak = measure_peak_dbfs(path)
    if peak is not None:
        lufs = measure_lufs(path)
        gain = gain_for(lufs, peak, target_lufs, ceiling_dbfs)
        apply_gain(path, gain)
    return measure_lufs(path), measure_peak_dbfs(path), probe_duration(path)


def _catalog_entry(mood, path, defaults, length_ms, log=print):
    lufs, peak, dur = _measure_and_normalise(mood, path, defaults, log=log)
    log(f"   {mood['id']}: dur={dur}s  lufs={lufs}  peak={peak}dBFS")
    return {
        "id": mood["id"],
        "file": f"tracks/{path.name}",
        "tones": mood.get("tones", []),
        "duration_s": dur,
        "requested_ms": length_ms,
        "loudness_lufs": lufs,
        "peak_dbfs": peak,
        "source": "elevenlabs:music",
        "model": defaults.get("model", "music_v2"),
        "prompt": mood.get("prompt", ""),
        "generated_at": _utc_now_iso(),
    }


def _write_catalog(library, catalog):
    library = Path(library)
    (library / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")


def generate(library, env=None, only=None, force=False, dry_run=False, length_s=None, log=print):
    """Fill in the missing tracks. Returns a summary dict; raises MusicLibraryError only for
    conditions that stop the whole run (missing key with real work to do, an HTTP failure)."""
    library = Path(library)
    env = env if env is not None else {}
    palette = load_palette(library)
    defaults = load_defaults(palette)

    todo, skipped = plan_work(palette, library, only=only, force=force)
    if skipped:
        log("skipping (library-first): " + ", ".join(skipped))
    if not todo:
        log("library is complete — nothing to generate")
        return {"written": [], "skipped": skipped}

    if dry_run:
        for mood in todo:
            length = length_s if length_s is not None else mood.get("duration_s", 60)
            log(f"  WOULD generate {mood['id']} -> tracks/{mood['id']}.mp3 ({length:.0f}s)")
        return {"written": [], "skipped": skipped, "planned": [m["id"] for m in todo]}

    api_key = (env.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        ids = ", ".join(m["id"] for m in todo)
        raise MusicLibraryError(
            f"ELEVENLABS_API_KEY not set — cannot generate {ids}. "
            "Supply licensed tracks in tracks/ instead, or set the key."
        )

    tracks_dir = library / "tracks"
    tracks_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(library)
    by_id = {t["id"]: t for t in catalog.get("tracks", [])}
    written = []

    try:
        for mood in todo:
            length = length_s if length_s is not None else mood.get("duration_s", 60)
            log(f"-> {mood['id']} ({length:.0f}s)")
            url, headers, body = build_request(mood, defaults, length_s=length_s)
            try:
                audio = _request_music(url, headers, body, api_key)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:400]
                raise MusicLibraryError(f"ElevenLabs HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                reason = str(exc)
                hint = ""
                if "CERTIFICATE_VERIFY_FAILED" in reason:
                    hint = (
                        " This looks like the python.org 3.14 installer not registering "
                        "system CA certificates. Run "
                        "`/Applications/Python 3.14/Install Certificates.command` once, "
                        "then retry."
                    )
                raise MusicLibraryError(f"ElevenLabs request failed: {reason}.{hint}") from exc
            if len(audio) < 1000:
                raise MusicLibraryError(
                    f"{mood['id']}: response too small ({len(audio)} bytes) — treating as an error"
                )
            path = tracks_dir / f"{mood['id']}.mp3"
            path.write_bytes(audio)
            length_ms = int(round(length * 1000))
            by_id[mood["id"]] = _catalog_entry(mood, path, defaults, length_ms, log=log)
            written.append(mood["id"])
    finally:
        catalog["tracks"] = list(by_id.values())
        _write_catalog(library, catalog)

    return {"written": written, "skipped": skipped}


def renormalise(library, only=None, log=print):
    """Re-balance existing tracks to the current target. No API call, no billing."""
    library = Path(library)
    palette = load_palette(library)
    defaults = load_defaults(palette)
    catalog = load_catalog(library)
    by_id = {t["id"]: t for t in catalog.get("tracks", [])}

    moods = palette.get("moods", [])
    if only:
        moods = [m for m in moods if m["id"] in only]

    n = 0
    for mood in moods:
        path = library / "tracks" / f"{mood['id']}.mp3"
        if not path.exists():
            continue
        length_ms = by_id.get(mood["id"], {}).get("requested_ms")
        by_id[mood["id"]] = _catalog_entry(mood, path, defaults, length_ms, log=log)
        n += 1

    catalog["tracks"] = list(by_id.values())
    _write_catalog(library, catalog)
    log(f"{n} tracks renormalised")
    return n


def _load_env():
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
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", default=str(DEFAULT_LIBRARY))
    ap.add_argument("--only", help="comma-separated mood ids")
    ap.add_argument("--length-s", type=float, default=None,
                    help="override every mood's duration_s (use the master's duration)")
    ap.add_argument("--force", action="store_true", help="regenerate even if a track exists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--renorm", action="store_true", help="re-balance existing tracks, no API call")
    args = ap.parse_args(argv)

    library = Path(args.library)
    only = args.only.split(",") if args.only else None
    env = _load_env()

    try:
        if args.renorm:
            renormalise(library, only=only)
            return 0
        generate(library, env=env, only=only, force=args.force,
                 dry_run=args.dry_run, length_s=args.length_s)
        return 0
    except MusicLibraryError as exc:
        print(f"gen_music: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
