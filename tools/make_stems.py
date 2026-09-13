#!/usr/bin/env python3
"""Full-length voice, SFX and music stems for a human editor or a single-layer revision.

    python3 tools/make_stems.py <project> [--voice] [--sfx] [--music] [--all]

`mix_sfx.py` and `mix_music.py` produce AUDITION files — the voice mixed with cues or a
bed, ducked, for judging in context. This tool produces the thing you hand to an editor
instead: three separate, full-length WAV tracks that all start at master 0.000 and run
the whole master duration, so each drags onto a timeline at zero with no nudging.

Nothing here is ducked and no track depends on another — ducking and blending are the
final mix's job (`mix_sfx.py --no-optional`, `mix_music.py`), not this one's. Per-cue
`gain_db` from the SFX plan and per-segment `gain_db` from the music plan ARE baked in,
because those are the shape of the pass, not a mix decision.

Stdlib only: json, subprocess, tempfile. ffmpeg/ffprobe decode, mix and measure.
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools import mix_music

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

SAMPLE_RATE = 48000
CHANNELS = 2
BATCH_SIZE = 30


class StemError(Exception):
    """A stem cannot be built as asked."""


def _finite_float(value, what):
    """float(value), rejecting NaN/Infinity — python's json module accepts those tokens
    and a non-finite number reaching an ffmpeg filtergraph produces silent garbage."""
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise StemError(f"{what}: not a number ({value!r})") from exc
    if not math.isfinite(f):
        raise StemError(f"{what}: not finite ({value!r})")
    return f


def sfx_batches(events, duration, batch=BATCH_SIZE):
    """Drop events at or past `duration`, then split what remains into batches of `batch`.

    Returns (batches, skipped) where `batches` is a list of event-lists and `skipped` is
    the count of events dropped for being past the end of the master.
    """
    usable = [e for e in events if _finite_float(e["at_s"], "sfx at_s") < duration]
    skipped = len(events) - len(usable)
    batches = [usable[i:i + batch] for i in range(0, len(usable), batch)]
    return batches, skipped


def music_filter(segments, duration):
    """Pure filter-graph builder for the music stem.

    Input stream [0:a] is expected to be a full-length `anullsrc` (so the stem is exactly
    `duration` long even when the segments do not cover it end to end); track inputs follow
    at [1:a], [2:a], ... in `segments` order. Returns (filter_str, n_segments); (None, 0)
    when there is nothing to lay down.
    """
    if not segments:
        return None, 0
    parts, labels = [], []
    for i, seg in enumerate(segments, start=1):
        length = seg["to_s"] - seg["from_s"]
        fade_in = seg.get("fade_in_s", 1.0)
        fade_out = seg.get("fade_out_s", 2.0)
        gain = seg.get("gain_db", 0.0)
        delay_ms = int(round(seg["from_s"] * 1000))
        parts.append(
            f"[{i}:a]atrim=0:{length:.3f},afade=t=in:d={fade_in},"
            f"afade=t=out:st={max(0.0, length - fade_out):.3f}:d={fade_out},"
            f"volume={gain}dB,adelay={delay_ms}:all=1[m{i}]"
        )
        labels.append(f"[m{i}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[musicmix]")
    parts.append(
        "[0:a][musicmix]amix=inputs=2:normalize=0,alimiter=limit=0.97:level=disabled[aout]"
    )
    return ";".join(parts), len(labels)


def _duration_of(path):
    if FFPROBE is None:
        raise StemError("ffprobe not found on PATH")
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise StemError(f"{Path(path).name}: unreadable duration") from exc


def _write_graph(filt, tmpdir, name="filter.txt"):
    """Write a filter-graph script inside a caller-owned TemporaryDirectory, so it is
    cleaned up when that directory goes away instead of leaking in the system temp dir."""
    path = Path(tmpdir) / name
    path.write_text(filt)
    return str(path)


def _run_ffmpeg(cmd):
    if FFMPEG is None:
        raise StemError("ffmpeg not found on PATH — nothing was built")
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise StemError(f"ffmpeg failed:\n{proc.stderr.strip()[-800:]}")


def build_voice(master, out, duration):
    """The master's own audio stream, resampled to 48k stereo, exactly `duration` long."""
    master = Path(master)
    if not master.exists():
        raise StemError(f"{master} not found")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # apad: a master whose audio stream is shorter than its video (or than the requested
    # stem duration) still yields a full-length stem — the pad is silence, then -t trims it
    # to exactly `duration`.
    filt = f"[0:a]aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo,apad[vout]"
    with tempfile.TemporaryDirectory() as tmp:
        graph = _write_graph(filt, tmp)
        cmd = [FFMPEG, "-y", "-v", "error", "-i", str(master),
               "-filter_complex_script", graph, "-map", "[vout]",
               "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le",
               "-t", f"{duration:.6f}", str(out)]
        _run_ffmpeg(cmd)
    print(f"voice stem: {master} -> {out} ({duration:.3f}s)")
    return str(out)


def build_sfx(project, plan_path, out, duration, batch=BATCH_SIZE):
    """Every SFX cue, delayed and gained, mixed onto a full-length silent bed. No duck."""
    project = Path(project)
    plan_path = Path(plan_path)
    try:
        plan = json.loads(plan_path.read_text())
    except FileNotFoundError as exc:
        raise StemError(f"no cue sheet at {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise StemError(f"{plan_path.name}: invalid JSON ({exc.msg})") from exc

    catalog_rel = plan.get("catalog", "media/sfx/library/catalog.json")
    catalog_path = Path(catalog_rel) if Path(catalog_rel).is_absolute() else project / catalog_rel
    try:
        catalog_data = json.loads(catalog_path.read_text())
    except FileNotFoundError as exc:
        raise StemError(f"no sfx catalog at {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise StemError(f"{catalog_path.name}: invalid JSON ({exc.msg})") from exc
    catalog = {c["id"]: c for c in catalog_data.get("clips", [])}

    events = plan.get("events", [])
    batches, skipped = sfx_batches(events, duration, batch=batch)

    missing = {e["sfx_id"] for b in batches for e in b if e["sfx_id"] not in catalog}
    if missing:
        raise StemError(f"missing clips: {', '.join(sorted(missing))}")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not batches:
        cmd = [FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", f"{duration:.6f}",
               "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo",
               "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le",
               "-t", f"{duration:.6f}", str(out)]
        _run_ffmpeg(cmd)
        print(f"sfx stem: 0 cues (skipped {skipped}) -> {out} ({duration:.3f}s)")
        return str(out)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        part_files = []
        for bi, batch_events in enumerate(batches):
            cmd = [FFMPEG, "-y", "-v", "error",
                   "-f", "lavfi", "-t", f"{duration:.6f}",
                   "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo"]
            for ev in batch_events:
                clip_rel = catalog[ev["sfx_id"]]["file"]
                clip_path = Path(clip_rel)
                if not clip_path.is_absolute():
                    clip_path = catalog_path.parent / clip_rel
                cmd += ["-i", str(clip_path)]

            parts, labels = [], ["[0:a]"]
            for i, ev in enumerate(batch_events, start=1):
                delay_ms = int(round(_finite_float(ev["at_s"], "sfx at_s") * 1000))
                gain = _finite_float(ev.get("gain_db", 0), "sfx gain_db")
                parts.append(
                    f"[{i}:a]aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo,"
                    f"adelay={delay_ms}:all=1,volume={gain}dB[e{i}]"
                )
                labels.append(f"[e{i}]")
            parts.append(
                f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[mix]"
            )
            graph = _write_graph(";".join(parts), tmp, name=f"filter_part{bi:02d}.txt")
            part_path = tmp / f"sfx_part{bi:02d}.wav"
            cmd += ["-filter_complex_script", graph, "-map", "[mix]",
                    "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le",
                    "-t", f"{duration:.6f}", str(part_path)]
            _run_ffmpeg(cmd)
            part_files.append(part_path)

        cmd = [FFMPEG, "-y", "-v", "error"]
        for p in part_files:
            cmd += ["-i", str(p)]
        if len(part_files) == 1:
            sum_filt = "[0:a]anull[mix]"
        else:
            sum_filt = "".join(f"[{i}:a]" for i in range(len(part_files))) + \
                f"amix=inputs={len(part_files)}:normalize=0:dropout_transition=0[mix]"
        graph = _write_graph(sum_filt, tmp, name="filter_final.txt")
        cmd += ["-filter_complex_script", graph, "-map", "[mix]",
                "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le",
                "-t", f"{duration:.6f}", str(out)]
        _run_ffmpeg(cmd)

    total_events = sum(len(b) for b in batches)
    print(f"sfx stem: {total_events} cues (skipped {skipped}) -> {out} ({duration:.3f}s)")
    return str(out)


def build_music(project, plan_path, out, duration):
    """Every music segment, gained and faded, mixed onto a full-length silent bed. No duck.

    Fail-soft like `mix_music.py`: a segment whose track file is missing is dropped with a
    warning rather than raising. Zero usable segments means no stem is built at all — this
    returns None rather than writing a silent file nobody asked for.
    """
    project = Path(project)
    plan_path = Path(plan_path)
    try:
        plan = json.loads(plan_path.read_text())
    except FileNotFoundError as exc:
        raise StemError(f"no music plan at {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise StemError(f"{plan_path.name}: invalid JSON ({exc.msg})") from exc

    usable = []
    for seg in plan.get("segments", []):
        track_path = Path(seg["track"])
        if not track_path.is_absolute():
            track_path = project / track_path
        if not track_path.exists():
            print(f"! {track_path}: missing — this segment was dropped", file=sys.stderr)
            continue
        seg = dict(seg)
        seg["_resolved_track"] = track_path
        usable.append(seg)

    if not usable:
        print("! no usable music track — no music stem was built", file=sys.stderr)
        return None

    # Delegate segment normalization to mix_music.py — same default gain (-22 dB), the
    # same float coercion of from_s/to_s (a JSON string works), the same trim to master
    # duration, and the same overlap check. Reimplementing this here would drift.
    try:
        resolved = mix_music.resolve_segments(usable, master_duration_s=duration)
    except mix_music.MusicError as exc:
        raise StemError(str(exc)) from exc

    for seg in resolved:
        seg["gain_db"] = _finite_float(seg.get("gain_db", mix_music.DEFAULT_GAIN_DB),
                                        "music gain_db")
        if "fade_in_s" in seg:
            seg["fade_in_s"] = _finite_float(seg["fade_in_s"], "music fade_in_s")
        if "fade_out_s" in seg:
            seg["fade_out_s"] = _finite_float(seg["fade_out_s"], "music fade_out_s")

    filt, n = music_filter(resolved, duration)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", f"{duration:.6f}",
               "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo"]
        for seg in resolved:
            cmd += ["-i", str(seg["_resolved_track"])]
        graph = _write_graph(filt, tmp)
        cmd += ["-filter_complex_script", graph, "-map", "[aout]",
                "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s24le",
                "-t", f"{duration:.6f}", str(out)]
        _run_ffmpeg(cmd)
    print(f"music stem: {n} segment(s) -> {out} ({duration:.3f}s)")
    return str(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--music", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    if not (args.voice or args.sfx or args.music or args.all):
        ap.print_usage(sys.stderr)
        return 2

    project = Path(args.project)
    master = project / "output" / "master.mp4"
    try:
        duration = _duration_of(master)
    except StemError as exc:
        print(f"make_stems: {exc}", file=sys.stderr)
        return 1

    stems_dir = project / "output" / "stems"
    results = []
    errors = []

    if args.all or args.voice:
        try:
            results.append(build_voice(master, stems_dir / "voice.wav", duration))
        except StemError as exc:
            errors.append(f"voice: {exc}")

    if args.all or args.sfx:
        try:
            results.append(build_sfx(project, project / "work" / "sfx-plan.json",
                                     stems_dir / "sfx.wav", duration))
        except StemError as exc:
            errors.append(f"sfx: {exc}")

    if args.all or args.music:
        try:
            r = build_music(project, project / "work" / "music-plan.json",
                            stems_dir / "music.wav", duration)
            if r:
                results.append(r)
        except StemError as exc:
            errors.append(f"music: {exc}")

    if results:
        print()
        for r in results:
            print(f"  {r}  {_duration_of(r):.3f}s")
    for e in errors:
        print(f"make_stems: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
