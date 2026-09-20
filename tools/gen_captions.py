#!/usr/bin/env python3
"""Build a kinetic caption plan from word timings this plugin already has.

    python3 tools/gen_captions.py <project-dir> [--force] [--print]

Word timings come from vo/vo-manifest.json (ElevenLabs, free) for anything ElevenLabs
spoke, or from AssemblyAI for platform-native dialogue that has no manifest words.
Highlight spans are chosen by tools/caption_keywords.score_spans() and capped per
scene so only a handful of pages ever carry a highlight. Nothing here invents a
timing: a scene with no timing source lands in `untimed` with a reason instead of a
guess.

By default the tool reuses an existing work/caption-plan.json and exits 0 without
rewriting it. Pass --force to regenerate. Re-running on unchanged inputs produces
byte-identical `scenes` and `untimed` — only `generated_at` is allowed to differ.

Stdlib only.
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.gen_subs import derive_keyterms, transcribe_assemblyai
from tools.caption_keywords import score_spans

DEFAULT_STYLE = {
    "combine_tokens_within_ms": 400,
    "max_lines": 3,
    "min_body_px": 32,
    "safe_margin_pct": 5,
}

# Approximation used only to bucket highlights per page for cap purposes. The real
# page split happens in the Remotion component (captionPages.mjs, Phase C).
WORDS_PER_PAGE = 6


class CaptionPlanError(Exception):
    """The caption plan cannot be built as asked."""


def _read_manifest(path):
    path = Path(path)
    try:
        text = path.read_text()
    except FileNotFoundError as exc:
        raise CaptionPlanError(f"{path} not found") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CaptionPlanError(f"{path.name} is not valid JSON: {exc.msg}") from exc


def _read_audio_plan(path):
    path = Path(path)
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {"scenes": []}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CaptionPlanError(f"{path.name} is not valid JSON: {exc.msg}") from exc


def _apply_caps(highlights, num_words):
    """At most one highlight per WORDS_PER_PAGE bucket, at most max(1, pages // 4)
    total. `highlights` must already be sorted by (-score, start_word) — the winner
    of each bucket, and of the overall cap, is whichever comes first in that order."""
    if not num_words or not highlights:
        return []
    pages = max(1, math.ceil(num_words / WORDS_PER_PAGE))
    allowed = max(1, pages // 4)

    kept = []
    used_pages = set()
    for h in highlights:
        if len(kept) >= allowed:
            break
        page = h["start_word"] // WORDS_PER_PAGE
        if page in used_pages:
            continue
        kept.append(h)
        used_pages.add(page)
    kept.sort(key=lambda h: h["start_word"])
    return kept


def build_caption_plan(project, style=None, api_key=None, keyterms=None):
    """Read vo/vo-manifest.json + work/audio-plan.json, score highlight spans, and
    return the work/caption-plan.json payload (not yet written to disk — see main())."""
    project = Path(project)
    style = {**DEFAULT_STYLE, **(style or {})}

    manifest = _read_manifest(project / "vo" / "vo-manifest.json")
    words_by_id = {item["id"]: item.get("words", []) for item in manifest.get("items", [])}

    audio_plan = _read_audio_plan(project / "work" / "audio-plan.json")
    kw = keyterms if keyterms is not None else derive_keyterms(project)

    scenes_out = []
    untimed = []
    for scene in audio_plan.get("scenes", []):
        scene_num = scene["scene"]
        for layer in scene.get("layers", []):
            if layer.get("kind") not in ("narration", "dialogue"):
                continue

            item_id = Path(layer.get("out", "")).stem
            offset_s = float(layer.get("at_s", 0.0))

            words = words_by_id.get(item_id)
            source = "elevenlabs"
            if not words:
                if api_key:
                    audio_path = project / layer.get("out", "")
                    asr = transcribe_assemblyai(audio_path, api_key, keyterms=kw)
                    words = asr.get("words")
                    source = "assemblyai"
                else:
                    words = None

            if not words:
                reason = ("no words in manifest and no ASSEMBLYAI_API_KEY" if not api_key
                          else "no words in manifest and AssemblyAI returned no words")
                untimed.append({"scene": scene_num, "reason": reason})
                continue

            highlights = score_spans(words, keyterms=kw)
            highlights = _apply_caps(highlights, len(words))

            scenes_out.append({
                "scene": scene_num,
                "vo_item_id": item_id,
                "offset_s": offset_s,
                "timing_source": source,
                "words": [{"text": w["text"], "start_ms": w["start_ms"], "end_ms": w["end_ms"]}
                          for w in words],
                "highlights": highlights,
            })

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "style": style,
        "scenes": scenes_out,
        "untimed": untimed,
    }


def format_sheet(plan):
    lines = [f"{len(plan['scenes'])} scene(s) captioned, {len(plan['untimed'])} untimed"]
    for scene in plan["scenes"]:
        lines.append(f"  scene {scene['scene']:>3}  [{scene['timing_source']:<10}] "
                     f"{len(scene['words'])} word(s), {len(scene['highlights'])} highlight(s)")
    if plan["untimed"]:
        lines.append("  ! untimed scenes (no timing source):")
        for item in plan["untimed"]:
            lines.append(f"    scene {item['scene']}: {item['reason']}")
    return "\n".join(lines)


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
    ap.add_argument("project")
    ap.add_argument("--force", action="store_true", help="regenerate even if the plan already exists")
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args(argv)
    project = Path(args.project)
    out_path = project / "work" / "caption-plan.json"

    if out_path.exists() and not args.force:
        print(f"work/caption-plan.json already exists; use --force to regenerate")
        return 0

    env = _load_env()
    api_key = env.get("ASSEMBLYAI_API_KEY")

    try:
        plan = build_caption_plan(project, api_key=api_key)
    except CaptionPlanError as exc:
        print(f"gen_captions: {exc}", file=sys.stderr)
        return 1

    print(format_sheet(plan))
    if args.show:
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2) + "\n")
    print("\nwrote work/caption-plan.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
