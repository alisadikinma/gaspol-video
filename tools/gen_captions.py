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
import difflib
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


# Punctuation stripped from BOTH ends of a token before alignment comparison —
# surrounding punctuation only, so an interior hyphen ("ANPR-nya") survives.
_ALIGN_PUNCT = ".,;:!?()[]{}\"'’‘"


def _align_norm(text):
    return text.strip(_ALIGN_PUNCT).lower()


def align_to_script(asr_words, script_text):
    """asr_words: [{"text", "start_ms", "end_ms"}] from the recognizer.
    script_text: this scene's narration, as written in av-script.md.

    Returns one record per SCRIPT word, in script order, shaped
    [{"text", "start_ms", "end_ms"}]. `text` is ALWAYS the script's word,
    never the recognizer's. Timing comes from the matched recognizer word;
    an unmatched script word is given a timing linearly interpolated between
    its nearest timed neighbours."""
    if not asr_words:
        raise CaptionPlanError("align_to_script: no recognizer words to align against")
    script_words = script_text.split()
    if not script_words:
        raise CaptionPlanError("align_to_script: script_text has no words to align")

    script_norms = [_align_norm(w) for w in script_words]
    asr_norms = [_align_norm(w["text"]) for w in asr_words]

    matcher = difflib.SequenceMatcher(None, script_norms, asr_norms, autojunk=False)
    anchors = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            si = i1 + offset
            aw = asr_words[j1 + offset]
            anchors[si] = (aw["start_ms"], aw["end_ms"])

    n = len(script_words)
    first_ms = asr_words[0]["start_ms"]
    last_ms = asr_words[-1]["end_ms"]

    times = [None] * n

    if not anchors:
        # Zero matches anywhere: spread the script's words evenly across the
        # recognizer's whole span. Never before its first word, never after its last.
        span = last_ms - first_ms
        slice_dur = span / n
        for i in range(n):
            times[i] = (first_ms + slice_dur * i, first_ms + slice_dur * (i + 1))
    else:
        anchor_indices = sorted(anchors)
        first_anchor = anchor_indices[0]
        last_anchor = anchor_indices[-1]
        head_clamp = (asr_words[0]["start_ms"], asr_words[0]["end_ms"])
        tail_clamp = (asr_words[-1]["start_ms"], asr_words[-1]["end_ms"])
        for i in range(n):
            if i in anchors:
                times[i] = anchors[i]
            elif i < first_anchor:
                # Leading unmatched run: clamp to the recognizer's first timing,
                # never extrapolated to before it.
                times[i] = head_clamp
            elif i > last_anchor:
                # Trailing unmatched run: clamp to the recognizer's last timing,
                # never extrapolated past it.
                times[i] = tail_clamp
            else:
                # Interior gap: linearly interpolate between the two nearest
                # timed neighbours, strictly inside their span.
                prev_idx = max(a for a in anchor_indices if a < i)
                next_idx = min(a for a in anchor_indices if a > i)
                gap_start = anchors[prev_idx][1]
                gap_end = anchors[next_idx][0]
                run_start = prev_idx + 1
                run_len = next_idx - run_start
                pos = i - run_start
                slice_dur = (gap_end - gap_start) / (run_len + 1)
                times[i] = (gap_start + slice_dur * (pos + 0.5),
                            gap_start + slice_dur * (pos + 1.5))

    return [{"text": script_words[i], "start_ms": times[i][0], "end_ms": times[i][1]}
            for i in range(n)]


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
            aligned = False
            if not words:
                if api_key:
                    audio_path = project / layer.get("out", "")
                    asr = transcribe_assemblyai(audio_path, api_key, keyterms=kw)
                    asr_words = asr.get("words")
                    if asr_words:
                        # The recognizer's own words never survive into the plan —
                        # only its timing does. See tools/gen_subs.py's module
                        # docstring for the rule this enforces.
                        try:
                            words = align_to_script(asr_words, layer.get("text", ""))
                        except CaptionPlanError as exc:
                            raise CaptionPlanError(f"scene {scene_num}: {exc}") from exc
                        source = "assemblyai"
                        aligned = True
                    else:
                        words = None
                else:
                    words = None

            if not words:
                reason = ("no words in manifest and no ASSEMBLYAI_API_KEY" if not api_key
                          else "no words in manifest and AssemblyAI returned no words")
                untimed.append({"scene": scene_num, "reason": reason})
                continue

            highlights = score_spans(words, keyterms=kw)
            highlights = _apply_caps(highlights, len(words))

            scene_record = {
                "scene": scene_num,
                "vo_item_id": item_id,
                "offset_s": offset_s,
                "timing_source": source,
                "words": [{"text": w["text"], "start_ms": w["start_ms"], "end_ms": w["end_ms"]}
                          for w in words],
                "highlights": highlights,
            }
            if aligned:
                scene_record["aligned"] = True
            scenes_out.append(scene_record)

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
