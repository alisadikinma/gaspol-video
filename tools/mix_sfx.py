#!/usr/bin/env python3
"""Mix the SFX cue sheet over a master, then prove the cues are audible.

    python3 tools/mix_sfx.py <project-dir> [--plan PATH] [--print] [--no-optional] [--no-duck]

A plan with no `catalog` key reads the shared library at
`${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/sfx/catalog.json`; a plan that names a catalog
uses that one, exactly as before.

An event may carry `"stack": [{"sfx_id", "offset_s", "gain_db"}]` instead of `sfx_id`: one
layered cue (sub boom + hit + tail). Each layer is mixed at `at_s + offset_s` (offset down to
-0.5s so a riser can lead), inherits `optional` and `note`, and takes the parent's gain unless
it sets its own. A stack is ONE cue for the density ceiling, `--no-optional` and the cue sheet.

Two halves, and the second is the one that matters. Mixing is ffmpeg work. The
audibility check is what stops a cue sheet that reads beautifully and cannot be heard:
after mixing, each cue window is compared against the voice-only reference in dB.

The measurement constants are not guesses. They come from the calibration in
claude-youtube-editor (see NOTICE) and are documented in 14-sfx-design.md:

  * a story-critical cue must add >= +4 dB, texture +1 to +3 dB
  * transients are measured in a ~0.3s window, because 0.6s dilutes a 50ms click to nothing
  * a riser is measured at its final third, where its energy actually is
  * a cue sitting fully under continuous speech measures +0 dB at ANY gain — accept it as
    felt-not-heard or delete it, never chase it with gain

Stdlib only: wave, array, subprocess. ffmpeg is used for decoding and mixing and its
absence degrades loudly.
"""

import argparse
import array
import json
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

# tools/ is not a package on sys.path when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import asset_home  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

# Window sizes. A transient needs a tight window or it averages away.
TRANSIENT_WINDOW_S = 0.3
SUSTAINED_WINDOW_S = 0.6

# Audibility thresholds, in dB added over the voice-only reference.
STORY_CRITICAL_DB = 4.0
TEXTURE_MIN_DB = 1.0

# Brand density ceiling: past this, everything should be marked optional.
DENSITY_PER_MIN = 12

# How far before the parent time a layer may lead, so a riser can build into the hit.
MIN_STACK_OFFSET_S = -0.5

TRANSIENT_HINTS = ("pop", "click", "snap", "stamp", "knock", "impact", "zap", "tick", "key")
RISER_HINTS = ("riser", "build", "swell", "rise")


class PlanError(Exception):
    """The cue sheet cannot be mixed as written."""


def _resolve(project, value):
    """Absolute stays absolute; a relative path is resolved against the project folder, never the cwd."""
    p = Path(value)
    return p if p.is_absolute() else Path(project) / p


class SfxPlan:
    def __init__(self, data, events, catalog, project, path, catalog_ref=None, cues=None):
        self.data = data
        self.catalog_ref = catalog_ref or data.get("catalog", "")
        self.events = events
        self.cues = len(events) if cues is None else cues
        self.catalog = catalog
        self.project = Path(project)
        self.path = Path(path)
        self.notes = []

    def clip_path(self, clip):
        """A catalog entry's file: absolute as written, else beside the catalog."""
        path = Path(clip["file"])
        return path if path.is_absolute() else Path(self.catalog_ref).parent / path


def window_for(sfx_id):
    """Transient sounds get the tight window; anything sustained gets the wide one."""
    name = (sfx_id or "").lower()
    return TRANSIENT_WINDOW_S if any(h in name for h in TRANSIENT_HINTS) else SUSTAINED_WINDOW_S


def _decode_to_wav(path, tmpdir):
    """Any audio or video file -> mono 48k wav we can read with the wave module."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        return str(path)
    if FFMPEG is None:
        raise PlanError(f"ffmpeg not available to decode {path.name}")
    out = Path(tmpdir) / f"{path.stem}.decoded.wav"
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(out)],
        check=True, capture_output=True,
    )
    return str(out)


def rms_dbfs(audio_path, at_s, window_s):
    """RMS of one window, in dBFS. -inf becomes -120 so arithmetic stays finite."""
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = _decode_to_wav(audio_path, tmp)
        with wave.open(wav_path, "rb") as w:
            rate = w.getframerate()
            channels = w.getnchannels()
            width = w.getsampwidth()
            if width != 2:
                raise PlanError(f"{Path(audio_path).name}: expected 16-bit audio")
            start = max(0, int(at_s * rate))
            count = max(1, int(window_s * rate))
            w.setpos(min(start, w.getnframes() - 1))
            frames = w.readframes(min(count, w.getnframes() - start))

    samples = array.array("h")
    samples.frombytes(frames)
    if channels > 1:
        samples = samples[::channels]
    if not samples:
        return -120.0
    mean_square = sum((s / 32768.0) ** 2 for s in samples) / len(samples)
    if mean_square <= 0:
        return -120.0
    return 20.0 * math.log10(math.sqrt(mean_square))


def measure_cue(audio_path, at_s, sfx_id, duration_s=None):
    """Measure a cue where its energy actually is.

    A riser builds, so measuring its onset reports silence. Everything else is measured
    at its start.
    """
    window = window_for(sfx_id)
    name = (sfx_id or "").lower()
    if duration_s and any(h in name for h in RISER_HINTS):
        at_s = at_s + (duration_s * 2.0 / 3.0)
        window = min(window, max(0.2, duration_s / 3.0))
    return rms_dbfs(audio_path, at_s, window)


def audibility_delta(voice_only, mixed, at_s, sfx_id, duration_s=None):
    """How many dB the cue actually added at its window. This is the number that decides."""
    before = measure_cue(voice_only, at_s, sfx_id, duration_s)
    after = measure_cue(mixed, at_s, sfx_id, duration_s)
    return round(after - before, 2)


def load_catalog(path):
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise PlanError(f"catalog is not valid JSON: {exc.msg}") from exc
    return {c["id"]: c for c in data.get("clips", [])}


def _finite(where, field, value):
    """A real, finite number or a PlanError naming where it came from."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{where}: {field} is not a number") from exc
    if not math.isfinite(number):
        raise PlanError(f"{where}: {field} must be a finite number, got {value!r}")
    return number


def _expand_stack(i, ev, at_s, catalog, master_duration_s):
    """One mix event per layer of a stacked cue, each at the parent time plus its offset."""
    if "sfx_id" in ev:
        raise PlanError(f"event {i}: has both sfx_id and stack — use one")
    layers = ev["stack"]
    if not isinstance(layers, list) or not layers:
        raise PlanError(f"event {i}: stack is empty — list at least one layer")
    expanded = []
    parent_gain = _finite(f"event {i}", "gain_db", ev.get("gain_db", 0))
    for n, layer in enumerate(layers, start=1):
        if not isinstance(layer, dict):
            raise PlanError(f"event {i}, layer {n}: must be an object with sfx_id")
        layer_id = layer.get("sfx_id")
        if layer_id not in catalog:
            raise PlanError(f"event {i}, layer {n}: sfx_id {layer_id!r} is not in the catalog")
        offset = _finite(f"event {i}, layer {n}", "offset_s", layer.get("offset_s", 0))
        gain = (_finite(f"event {i}, layer {n}", "gain_db", layer["gain_db"])
                if "gain_db" in layer else parent_gain)
        if offset < MIN_STACK_OFFSET_S:
            raise PlanError(
                f"event {i}, layer {n}: offset_s {offset} is earlier than {MIN_STACK_OFFSET_S}s"
            )
        layer_at = at_s + offset
        if layer_at < 0:
            raise PlanError(f"event {i}, layer {n}: lands at {layer_at:.2f}s, before the start")
        if master_duration_s is not None and layer_at > master_duration_s:
            raise PlanError(
                f"event {i}, layer {n}: lands at {layer_at:.2f}s, past the end of the master "
                f"({master_duration_s:.2f}s)"
            )
        expanded.append({
            **{k: v for k, v in ev.items() if k != "stack"},
            "sfx_id": layer_id,
            "at_s": layer_at,
            "gain_db": gain,
            "clip": catalog[layer_id],
            "stack_ref": {"event": i, "size": len(layers), "parent_at_s": at_s},
        })
    return expanded


def load_plan(plan_path, project, master_duration_s=None, include_optional=True):
    plan_path = Path(plan_path)
    try:
        data = json.loads(plan_path.read_text())
    except FileNotFoundError as exc:
        raise PlanError(f"no cue sheet at {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"{plan_path.name} is not valid JSON: line {exc.lineno}, {exc.msg}") from exc

    catalog_ref = data.get("catalog") or str(asset_home.library("sfx") / "catalog.json")
    catalog = load_catalog(catalog_ref if Path(catalog_ref).is_absolute()
                           else Path(project) / catalog_ref)

    events = []
    cues = 0
    for i, ev in enumerate(data.get("events", []), start=1):
        if not include_optional and ev.get("optional"):
            continue
        try:
            at_s = float(ev["at_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanError(f"event {i}: at_s missing or not a number") from exc
        if not math.isfinite(at_s):
            raise PlanError(f"event {i}: at_s must be a finite number, got {ev['at_s']!r}")
        if at_s < 0:
            raise PlanError(f"event {i}: at_s is negative ({at_s})")
        if master_duration_s is not None and at_s > master_duration_s:
            raise PlanError(
                f"event {i}: at_s {at_s} is past the end of the master ({master_duration_s:.2f}s)"
            )
        if "stack" in ev:
            events.extend(_expand_stack(i, ev, at_s, catalog, master_duration_s))
            cues += 1
            continue
        sfx_id = ev.get("sfx_id")
        if sfx_id not in catalog:
            raise PlanError(
                f"event {i}: sfx_id {sfx_id!r} is not in the catalog — "
                "add a recipe to palette.json and run gen_sfx.py, or reuse an existing clip"
            )
        gain = _finite(f"event {i}", "gain_db", ev.get("gain_db", 0))
        events.append({**ev, "at_s": at_s, "gain_db": gain, "clip": catalog[sfx_id]})
        cues += 1

    plan = SfxPlan(data, events, catalog, project, plan_path, catalog_ref=catalog_ref, cues=cues)

    if not cues:
        plan.notes.append("no cues in this plan — nothing will be mixed")
    if master_duration_s:
        per_min = cues / (master_duration_s / 60.0)
        if per_min > DENSITY_PER_MIN:
            plan.notes.append(
                f"density {per_min:.1f} cues/min is over the {DENSITY_PER_MIN}/min ceiling — "
                "mark the deniable ones optional: true"
            )
    return plan


def _event_line(number, at_s, label, ev):
    flag = " (optional)" if ev.get("optional") else ""
    scene = f"scene {ev['scene']}" if ev.get("scene") else ""
    return (f"  {number:>3}. {at_s:>8.2f}s  {label:<22} {ev.get('gain_db', 0):>+5} dB  "
            f"{scene:<9} {ev.get('cue', '')}{flag}")


def format_sheet(plan):
    lines = [f"{plan.path.name}: {plan.cues} cue(s)"]
    number = 0
    seen_stacks = set()
    for ev in plan.events:
        ref = ev.get("stack_ref")
        if ref is None:
            number += 1
            lines.append(_event_line(number, ev["at_s"], ev["sfx_id"], ev))
            continue
        if ref["event"] not in seen_stacks:
            seen_stacks.add(ref["event"])
            number += 1
            names = "+".join(e["sfx_id"] for e in plan.events
                             if e.get("stack_ref", {}).get("event") == ref["event"])
            lines.append(_event_line(number, ref["parent_at_s"], f"stack({ref['size']}): {names}", ev))
        lines.append(f"         {ev['at_s']:>8.2f}s  {ev['sfx_id']:<22} {ev.get('gain_db', 0):>+5} dB")
    for note in plan.notes:
        lines.append(f"  ! {note}")
    return "\n".join(lines)


def master_duration(path):
    if FFPROBE is None:
        return None
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def build_filter(plan, duck=True):
    """One delayed, gained input per cue, summed, then optionally ducked under the voice."""
    parts = []
    labels = []
    for i, ev in enumerate(plan.events, start=1):
        delay_ms = int(ev["at_s"] * 1000)
        gain = ev.get("gain_db", 0)
        parts.append(
            f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={gain}dB[s{i}]"
        )
        labels.append(f"[s{i}]")
    if not labels:
        return None
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[sfxmix]")
    if duck:
        # The voice keys the compressor, so cues step back while someone is speaking.
        parts.append("[sfxmix][0:a]sidechaincompress=threshold=0.05:ratio=6:attack=5:release=250[ducked]")
        parts.append("[0:a][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")
    else:
        parts.append("[0:a][sfxmix]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")
    return ";".join(parts)


def mix(plan, out=None, duck=True):
    if FFMPEG is None:
        print("ffmpeg not found on PATH — nothing was mixed. The cue sheet above is still the "
              "deliverable; run the mix elsewhere.", file=sys.stderr)
        return None
    master = plan.project / plan.data.get("master", "output/master.mp4")
    out_path = Path(out) if out else plan.project / plan.data.get("render", {}).get(
        "out", "output/master-mixed.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    filt = build_filter(plan, duck=duck)
    if filt is None:
        print("no cues to mix")
        return None

    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(master)]
    for ev in plan.events:
        cmd += ["-i", str(plan.clip_path(ev["clip"]))]
    cmd += ["-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", str(out_path)]

    print("+ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PlanError(f"mix failed:\n{proc.stderr.strip()[-800:]}")
    return str(out_path)


def report_audibility(plan, voice_only, mixed):
    """The table that decides whether a cue stays. Printed after every mix."""
    lines = ["cue audibility (dB added over the voice-only reference):"]
    for ev in plan.events:
        delta = audibility_delta(voice_only, mixed, ev["at_s"], ev["sfx_id"],
                                 ev["clip"].get("duration_s"))
        if delta >= STORY_CRITICAL_DB:
            verdict = "clear"
        elif delta >= TEXTURE_MIN_DB:
            verdict = "texture"
        else:
            verdict = "INAUDIBLE"
        lines.append(f"  {ev['at_s']:>8.2f}s  {ev['sfx_id']:<22} {delta:>+6.2f} dB  {verdict}")
    lines.append(
        "  note: a cue sitting fully under continuous speech measures +0 dB at any gain. "
        "Accept it as felt-not-heard or delete it; do not chase it with gain."
    )
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--plan", help="default: <project>/work/sfx-plan.json; relative = inside the project")
    ap.add_argument("--print", dest="show", action="store_true", help="print the cue sheet only")
    ap.add_argument("--no-optional", action="store_true", help="drop cues marked optional")
    ap.add_argument("--no-duck", action="store_true", help="skip the sidechain duck")
    ap.add_argument("--out", help="override the output path")
    args = ap.parse_args(argv)

    project = Path(args.project)
    plan_path = _resolve(project, args.plan) if args.plan else project / "work" / "sfx-plan.json"
    out_arg = str(_resolve(project, args.out)) if args.out else None

    try:
        if not plan_path.is_file():
            raise PlanError(f"no cue sheet at {plan_path}")
        probe_master = project / json.loads(plan_path.read_text()).get("master", "output/master.mp4")
        duration = master_duration(probe_master)
        plan = load_plan(plan_path, project, master_duration_s=duration,
                         include_optional=not args.no_optional)
        print(format_sheet(plan))
        if args.show:
            return 0
        mixed = mix(plan, out=out_arg, duck=not args.no_duck)
        if mixed:
            print()
            print(report_audibility(plan, probe_master, mixed))
        return 0
    except PlanError as exc:
        print(f"mix_sfx: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
