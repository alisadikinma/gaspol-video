#!/usr/bin/env python3
"""Grow the shared music-bed library from palette.json mood recipes.

    python3 tools/gen_music.py [--library DIR] [--recipes FILE] [--only id1,id2]
                                [--length-s N] [--force] [--dry-run] [--renorm]
    python3 tools/gen_music.py video <project> [--master output/master.mp4] [--tags a,b]
                                [--model music_v2] [--description-file F] [--force] [--dry-run]

Tracks are written to `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/music` so a plugin update
never loses them; mood recipes are read from the plugin's `media/music/library/palette.json`.
An explicit `--library DIR` keeps the old behaviour: tracks go to DIR, palette read from DIR.
Earlier plugin versions' tracks are copied into the home library on the first real run.

LIBRARY-FIRST: a mood whose tracks/<id>.mp3 already exists is skipped and never re-billed,
unless --force. Tracks are generated with ElevenLabs Music (force_instrumental) and
loudness-normalised toward the palette's target LUFS, clamped so the peak never crosses the
ceiling — the same shape as tools/gen_sfx.py, one octave down (minutes, not seconds).

`--renorm` re-balances existing tracks to the current target without calling the API.

Stdlib only. Missing key or missing ffmpeg degrades loudly and names what could not be made.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# tools/ is not a package on sys.path when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import asset_home, renders  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
API_URL = "https://api.elevenlabs.io/v1/music"

# Video-to-music (GV-8): a bed composed to the edited master's picture.
V2M_URL = "https://api.elevenlabs.io/v1/music/video-to-music"
V2M_MAX_S = 600
V2M_MAX_BYTES = 200 * 1024 * 1024
V2M_MAX_DESCRIPTION = 1000
V2M_MAX_TAGS = 10
V2M_MODELS = ("music_v1", "music_v2", "music_v2_5")

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


def load_palette(library, recipes=None):
    path = Path(recipes) if recipes else Path(library) / "palette.json"
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


def build_video_music_request(proxy_bytes, description, tags, model,
                              output_format="mp3_44100_128"):
    """Pure multipart request for /v1/music/video-to-music — no API key here, so it is testable
    without one. The caller adds xi-api-key at send time."""
    tags = list(tags or [])
    if model not in V2M_MODELS:
        raise MusicLibraryError(f"unknown model: {model} (use one of {', '.join(V2M_MODELS)})")
    if len(tags) > V2M_MAX_TAGS:
        raise MusicLibraryError(f"too many tags: {len(tags)} (max {V2M_MAX_TAGS})")
    if description is not None and not 1 <= len(description) <= V2M_MAX_DESCRIPTION:
        raise MusicLibraryError(
            f"description must be 1-{V2M_MAX_DESCRIPTION} chars, got {len(description)}")

    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    parts = [(f'Content-Disposition: form-data; name="videos"; filename="master.mp4"\r\n'
              f"Content-Type: video/mp4\r\n").encode("utf-8"), proxy_bytes]
    fields = []
    if description:
        fields.append(("description", description))
    fields.extend(("tags", tag) for tag in tags)
    fields.append(("model_id", model))
    for name, value in fields:
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n'.encode("utf-8"))
        parts.append(value.encode("utf-8"))

    body = b""
    for i in range(0, len(parts), 2):
        body += f"--{boundary}\r\n".encode("utf-8") + parts[i] + crlf + parts[i + 1] + crlf
    body += f"--{boundary}--\r\n".encode("utf-8")
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "audio/mpeg"}
    return f"{V2M_URL}?output_format={output_format}", headers, body


def make_proxy(master, dest):
    """Picture-only, at most 1280px, small: what video-to-music needs to see, well under the
    200 MB limit. The master's audio is dropped on purpose — the model composes to the picture."""
    if FFMPEG is None:
        raise MusicLibraryError("ffmpeg not found on PATH — cannot build the picture-only proxy")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-i", str(master), "-an",
         "-vf", "scale=w=1280:h=1280:force_original_aspect_ratio=decrease:force_divisible_by=2",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(dest)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 or not dest.exists():
        raise MusicLibraryError(f"ffmpeg could not build the proxy: {proc.stderr.strip()[-300:]}")
    return dest


def _music_direction_lines(text):
    """Direction text from lines starting `music:` / `musik:` (list markers and bold ignored)
    and from cells under a `Music` / `Musik` table column."""
    found = []
    column = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            lowered = [c.lower().strip("* ") for c in cells]
            if column is None:
                for name in ("music", "musik"):
                    if name in lowered:
                        column = lowered.index(name)
                        break
                continue
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            if column < len(cells) and cells[column] not in ("", "-"):
                found.append(cells[column])
            continue
        column = None
        plain = re.sub(r"^[-*+]\s+", "", line).replace("**", "")
        m = re.match(r"(?i)(?:music|musik)\s*:\s*(.+)$", plain)
        if m:
            found.append(m.group(1).strip())
    return found


def default_description(project):
    """The script's music direction as a video-to-music description, or None when the script
    names none. Truncated to the API's 1000 characters on a word boundary."""
    try:
        text = (Path(project) / "av-script.md").read_text()
    except OSError:
        return None
    joined = "; ".join(_music_direction_lines(text))
    if not joined:
        return None
    return _clip_description(joined)


def _clip_description(text):
    if len(text) <= V2M_MAX_DESCRIPTION:
        return text
    cut = text[:V2M_MAX_DESCRIPTION]
    if not text[V2M_MAX_DESCRIPTION].isspace():
        cut = cut.rsplit(None, 1)[0]
    return cut.rstrip()


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


def generate(library, env=None, only=None, force=False, dry_run=False, length_s=None, log=print,
             recipes=None):
    """Fill in the missing tracks. Returns a summary dict; raises MusicLibraryError only for
    conditions that stop the whole run (missing key with real work to do, an HTTP failure)."""
    library = Path(library)
    env = env if env is not None else {}
    palette = load_palette(library, recipes)
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


def renormalise(library, only=None, log=print, recipes=None):
    """Re-balance existing tracks to the current target. No API call, no billing."""
    library = Path(library)
    palette = load_palette(library, recipes)
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


V2M_MUSIC_FILE = "output/music.mp3"


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plugin_defaults():
    try:
        return load_defaults(load_palette(None, asset_home.recipes("music")))
    except MusicLibraryError:
        return dict(FALLBACK_DEFAULTS)


def _network_reason(exc):
    reason = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in reason:
        reason += (
            ". This looks like the python.org 3.14 installer not registering system CA "
            "certificates. Run `/Applications/Python 3.14/Install Certificates.command` "
            "once, then retry.")
    return reason


def run_video_music(project, master="output/master.mp4", description_file=None, tags=(),
                    model="music_v2", force=False, dry_run=False, sender=None, env=None,
                    log=print):
    """Compose a bed to the master. Returns 0 (written, up-to-date or dry-run), 1 (bad
    input) or 3 (fall back to the palette; the reason is logged). Never raises past here."""
    project = Path(project)
    sender = sender or _request_music
    env = env if env is not None else _load_env()
    master_path = project / master
    proxy_path = project / ".tmp" / "music-proxy.mp4"
    out_path = project / V2M_MUSIC_FILE

    def fallback(reason, sent=False, prompt_hash=""):
        log(f"FALLBACK palette: {reason}")
        if sent:
            renders.record(project, {
                "file": V2M_MUSIC_FILE, "phase": "6", "scene": None, "model": model,
                "prompt_sha256": prompt_hash, "refs": [], "status": "failed",
                "error": reason, "cdn_url": None})
        return 3

    if not master_path.is_file():
        return fallback("master not found")

    if description_file:
        try:
            description = _clip_description(Path(description_file).read_text().strip()) or None
        except OSError as exc:
            log(f"gen_music: cannot read --description-file: {exc}")
            return 1
    else:
        description = default_description(project)
    tags = list(tags)
    request_key = json.dumps({"master_sha256": _sha256_file(master_path),
                              "description": description, "tags": tags, "model": model},
                             sort_keys=True)
    prompt_hash = renders.prompt_sha256(request_key)

    if not force and out_path.exists():
        try:
            fresh = not renders.needs_render(renders.load(project), V2M_MUSIC_FILE, request_key)
        except renders.RenderLedgerError:
            fresh = False
        if fresh:
            log(f"up-to-date: {V2M_MUSIC_FILE} (master unchanged)")
            return 0

    duration = probe_duration(master_path)
    if duration is not None and duration > V2M_MAX_S:
        return fallback(f"master is {duration:.0f}s, video-to-music accepts up to {V2M_MAX_S}s")

    try:
        try:
            make_proxy(master_path, proxy_path)
        except MusicLibraryError as exc:
            return fallback(str(exc))
        size = proxy_path.stat().st_size
        if size > V2M_MAX_BYTES:
            return fallback(f"proxy is {size / 1048576:.0f} MB, limit 200 MB")
        api_key = (env.get("ELEVENLABS_API_KEY") or "").strip()
        if not api_key:
            return fallback("ELEVENLABS_API_KEY not set")

        try:
            url, headers, body = build_video_music_request(
                proxy_path.read_bytes(), description, tags, model)
        except MusicLibraryError as exc:
            log(f"gen_music: {exc}")
            return 1

        if dry_run:
            log(f"WOULD request video-to-music: {size / 1048576:.1f} MB, "
                f"{duration if duration is not None else '?'}s, model {model}, {len(tags)} tags")
            return 0

        # One attempt only: after an ambiguous failure billing may have happened, so the
        # user re-runs deliberately instead of the tool retrying.
        try:
            audio = sender(url, headers, body, api_key)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:200]
            if exc.code == 403:
                reason = "HTTP 403 \u2014 this ElevenLabs plan has no Music access"
            elif exc.code == 422:
                reason = f"HTTP 422 \u2014 {detail}"
            else:
                reason = f"HTTP {exc.code} \u2014 {detail}"
            return fallback(reason, sent=True, prompt_hash=prompt_hash)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return fallback(f"network error: {_network_reason(exc)}", sent=True,
                            prompt_hash=prompt_hash)
        if len(audio) < 1000:
            return fallback(f"response too small ({len(audio)} bytes)", sent=True,
                            prompt_hash=prompt_hash)

        staged = project / ".tmp" / "music-new.mp3"
        staged.write_bytes(audio)
        _measure_and_normalise({"id": "music"}, staged, _plugin_defaults(), log=log)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, out_path)
        renders.record(project, {
            "file": V2M_MUSIC_FILE, "phase": "6", "scene": None, "model": model,
            "prompt_sha256": prompt_hash, "refs": [], "status": "done",
            "error": None, "cdn_url": None})
        length = probe_duration(out_path)
        shown = f"{length:.2f}s" if length is not None else "duration unknown"
        log(f'wrote {V2M_MUSIC_FILE} ({shown}) \u2014 set music-plan.json "bed_source": "video"')
        return 0
    except (OSError, renders.RenderLedgerError) as exc:
        return fallback(f"{type(exc).__name__}: {exc}")
    finally:
        if not dry_run:
            proxy_path.unlink(missing_ok=True)


def main_video(argv, sender=None, env=None, log=print):
    """`gen_music.py video <project>` — see the module docstring."""
    ap = argparse.ArgumentParser(
        prog="gen_music.py video",
        description="Compose a music bed to the edited master with ElevenLabs video-to-music. "
                    "Exit 3 means fall back to the palette.")
    ap.add_argument("project", help="the {output_folder} holding output/ and av-script.md")
    ap.add_argument("--master", default="output/master.mp4", help="master, relative to the project")
    ap.add_argument("--description-file", help="text file to use instead of the script's music lines")
    ap.add_argument("--tags", default="", help="comma-separated, at most 10")
    ap.add_argument("--model", default="music_v2", choices=V2M_MODELS)
    ap.add_argument("--force", action="store_true", help="request even if the master is unchanged")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    return run_video_music(
        args.project, master=args.master, description_file=args.description_file, tags=tags,
        model=args.model, force=args.force, dry_run=args.dry_run, sender=sender, env=env, log=log)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["video"]:
        return main_video(argv[1:])
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="For a bed composed to the edited master: gen_music.py video --help")
    ap.add_argument("--library", help="default: ${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/music")
    ap.add_argument("--recipes", help="palette.json; default: the plugin's, or DIR's when --library is given")
    ap.add_argument("--only", help="comma-separated mood ids")
    ap.add_argument("--length-s", type=float, default=None,
                    help="override every mood's duration_s (use the master's duration)")
    ap.add_argument("--force", action="store_true", help="regenerate even if a track exists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--renorm", action="store_true", help="re-balance existing tracks, no API call")
    args = ap.parse_args(argv)

    library = Path(args.library) if args.library else asset_home.library("music")
    recipes = args.recipes or (None if args.library else asset_home.recipes("music"))
    only = args.only.split(",") if args.only else None
    env = _load_env()

    try:
        if args.renorm:
            renormalise(library, only=only, recipes=recipes)
            return 0
        if not args.dry_run and not args.library:
            asset_home.adopt("music")
        generate(library, env=env, only=only, force=args.force,
                 dry_run=args.dry_run, length_s=args.length_s, recipes=recipes)
        return 0
    except MusicLibraryError as exc:
        print(f"gen_music: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
