#!/usr/bin/env python3
"""Turn a topic, a tone and a beat arc into one music prompt per segment.

    python3 tools/music_brief.py <project-dir> [--brief work/music-brief.json] [--print]

Reads `work/music-brief.json` (written by the post skill from `strategic-brief.md` and
`av-script.md`) and writes `work/music-palette.json` plus the segments of
`work/music-plan.json`. Generate the tracks with
`gen_music.py --recipes <project>/work/music-palette.json --only <ids>`; that step bills, this one does not.

The prompt text comes from the brief, not from a fixed mood list, so a port film and a hospital
film no longer share one bed. The id is a hash of prompt and length: an unchanged segment keeps
its id, finds its track in the library and is never billed twice.

Stdlib only.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PALETTE_DEFAULTS = PLUGIN_ROOT / "media" / "music" / "library" / "palette.json"

PROMPT_CAP = 400
# ElevenLabs accepts music_length_ms 3,000 to 600,000 (docs checked 2026-10-16). These tighter
# bounds keep a bed useful as one track; a longer segment loops in mix_music.fit_track.
MIN_LENGTH_S = 10
MAX_LENGTH_S = 120

TAIL = "instrumental, no vocals, leaves room for a speaking voice"

TONE_WORDS = {
    "Serious": "restrained low pulse, documentary tension",
    "Inspirational": "warm rising strings and piano, hopeful",
    "Humorous": "playful light pizzicato, bouncy",
    "Professional": "clean modern underscore, steady light pulse",
    "Casual": "relaxed soft groove, airy",
    "Edgy": "tight driving synth, modern, punchy",
}

BEAT_WORDS = {
    "hook": "immediate, attention-grabbing, strong first second",
    "build": "gradually rising tension",
    "body": "steady supportive bed",
    "peak": "swelling to the loudest moment, then clean stop",
    "resolve": "releasing, settling, warm",
    "cta": "confident resolving lift",
}

ENERGY_WORDS = {
    1: "very low energy",
    2: "low energy",
    3: "medium energy",
    4: "high energy",
    5: "maximum energy",
}


class BriefError(Exception):
    """The music brief cannot be turned into prompts as written."""


def _join(parts):
    return ", ".join(p for p in parts if p)


def build_prompt(brief, segment):
    tone = TONE_WORDS[brief["tone"]]
    beat = BEAT_WORDS[segment["beat"]]
    world = str(brief["sound_world"]).strip()
    energy = ENERGY_WORDS[segment["energy"]]

    prompt = _join([tone, beat, world, energy, TAIL])
    if len(prompt) <= PROMPT_CAP:
        return prompt
    prompt = _join([tone, beat, world, TAIL])
    if len(prompt) <= PROMPT_CAP:
        return prompt
    # Trim the world, keep the tail: it carries the no-vocals instruction. Two extra characters
    # are the ", " that joins the world to its neighbours.
    room = max(PROMPT_CAP - len(_join([tone, beat, TAIL])) - 2, 0)
    return _join([tone, beat, world[:room].rstrip(", "), TAIL])


def mood_id(prompt, length_s):
    digest = hashlib.sha256(f"{prompt}|{round(length_s)}".encode("utf-8")).hexdigest()
    return "brief-" + digest[:10]


def segment_length_s(segment):
    raw = float(segment["to_s"]) - float(segment["from_s"])
    return min(max(raw, MIN_LENGTH_S), MAX_LENGTH_S)


def _text(brief, field):
    value = brief.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BriefError(f"{field}: missing or empty")
    return value


def validate(brief):
    if not isinstance(brief, dict):
        raise BriefError("brief: must be a JSON object")
    for field in ("topic", "domain", "sound_world"):
        _text(brief, field)
    if brief.get("tone") not in TONE_WORDS:
        raise BriefError(f"tone: {brief.get('tone')!r} is not one of {', '.join(TONE_WORDS)}")
    segments = brief.get("segments")
    if not isinstance(segments, list) or not segments:
        raise BriefError("segments: need at least one segment")

    spans = []
    for i, seg in enumerate(segments, start=1):
        if not isinstance(seg, dict):
            raise BriefError(f"segment {i}: must be an object")
        times = {}
        for field in ("from_s", "to_s"):
            value = seg.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BriefError(f"segment {i}: {field} missing or not a number")
            if not math.isfinite(value):
                raise BriefError(f"segment {i}: {field} must be a finite number, got {value}")
            times[field] = float(value)
        if times["to_s"] <= times["from_s"]:
            raise BriefError(
                f"segment {i}: to_s {times['to_s']} is not after from_s {times['from_s']}")
        if seg.get("beat") not in BEAT_WORDS:
            raise BriefError(f"segment {i}: beat {seg.get('beat')!r} is not one of "
                             f"{', '.join(BEAT_WORDS)}")
        energy = seg.get("energy")
        if isinstance(energy, bool) or energy not in ENERGY_WORDS:
            raise BriefError(f"segment {i}: energy {energy!r} must be a whole number 1-5")
        spans.append((times["from_s"], times["to_s"], i))

    spans.sort()
    for (_, a_end, a_i), (b_start, _, b_i) in zip(spans, spans[1:]):
        if b_start < a_end - 1e-6:
            raise BriefError(f"segments overlap: segment {a_i} ends at {a_end}s, "
                             f"segment {b_i} starts at {b_start}s")


def build_outputs(brief):
    """Pure: (palette, plan segments) for a validated brief."""
    defaults = json.loads(PALETTE_DEFAULTS.read_text(encoding="utf-8")).get("defaults", {})
    moods, segments = [], []
    for seg in sorted(brief["segments"], key=lambda s: s["from_s"]):
        prompt = build_prompt(brief, seg)
        length = segment_length_s(seg)
        mid = mood_id(prompt, length)
        moods.append({"id": mid, "tones": [brief["tone"]], "prompt": prompt, "duration_s": length})
        segments.append({"from_s": seg["from_s"], "to_s": seg["to_s"], "track": f"library:{mid}"})
    palette = {
        "_comment": "Written by tools/music_brief.py from work/music-brief.json. "
                    "Generate with gen_music.py --recipes <project>/work/music-palette.json --only <ids>.",
        "defaults": defaults,
        "moods": moods,
    }
    return palette, segments


def _load_brief(path):
    path = Path(path)
    if not path.exists():
        raise BriefError(f"brief not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BriefError(f"{path.name} is not valid JSON: {exc}") from exc


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("--brief", default="work/music-brief.json")
    ap.add_argument("--print", action="store_true", dest="show",
                    help="print the segment table and write nothing")
    args = ap.parse_args(argv)

    project = Path(args.project)
    try:
        brief = _load_brief(project / args.brief)
        validate(brief)
        palette, segments = build_outputs(brief)
    except BriefError as exc:
        print(f"music_brief: {exc}", file=sys.stderr)
        return 2

    if args.show:
        beats = [s["beat"] for s in sorted(brief["segments"], key=lambda s: s["from_s"])]
        for seg, beat, mood in zip(segments, beats, palette["moods"]):
            print(f"{seg['from_s']:g}-{seg['to_s']:g}s  {beat:<7} {mood['id']}  {mood['prompt']}")
        return 0

    work = project / "work"
    plan_path = work / "music-plan.json"
    plan = {"out": "output/master-mixed.mp4"}
    if plan_path.exists():
        try:
            existing = json.loads(plan_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            print(f"music_brief: {plan_path.name} is not valid JSON, nothing written: {exc}",
                  file=sys.stderr)
            return 2
        if not isinstance(existing, dict):
            print(f"music_brief: {plan_path.name} must be a JSON object, nothing written",
                  file=sys.stderr)
            return 2
        plan = existing
        if plan.get("bed_source") == "video":
            print('music_brief: warning: plan has bed_source "video"; its segments were '
                  "replaced by the palette segments from this brief", file=sys.stderr)
    plan["segments"] = segments
    plan.setdefault("out", "output/master-mixed.mp4")
    try:
        _write_atomic(work / "music-palette.json",
                      json.dumps(palette, indent=2, ensure_ascii=False) + "\n")
        _write_atomic(plan_path, json.dumps(plan, indent=2) + "\n")
    except OSError as exc:
        print(f"music_brief: could not write: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(segments)} segments: {work / 'music-palette.json'}, {plan_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
