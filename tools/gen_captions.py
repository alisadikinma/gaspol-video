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
from tools.burn_subs import check_contrast, StyleError, _luminance

# WCAG AA's large-text threshold, not burn_subs.MIN_CONTRAST_RATIO (4.5) — the text
# drawn on a kinetic-caption highlight box is never small (the floor is 32px and the
# active line renders far above it), so the looser large-text floor is the correct
# standard here, not a re-derivation of burn_subs' own 4.5 rule.
HIGHLIGHT_TEXT_MIN_CONTRAST_RATIO = 3.0

DEFAULT_STYLE = {
    "combine_tokens_within_ms": 400,
    "max_lines": 3,
    "min_body_px": 32,
    "safe_margin_pct": 5,
}

# Approximation used only to bucket highlights per page for cap purposes. The real
# page split happens in the Remotion component (captionPages.mjs, Phase C).
WORDS_PER_PAGE = 6

# A title card holds for this many seconds from its scene's start, clamped to the
# scene's own length when the scene is shorter (Phase D). Matches
# templates/remotion/TitleCard.template.tsx's HOLD_S.
TITLE_CARD_HOLD_S = 2.5

_TITLE_CARD_SIDES = ("left", "right")


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


def _read_scene_plan_title_cards(project):
    """Parse scene-plan.md's `Title Card` column, keyed by scene number.

    Returns {scene_num: raw_cell_text}. A project with no scene-plan.md yet, or a
    scene-plan.md whose table has no `Title Card` column, yields an empty dict —
    title cards are optional, most scenes never carry one."""
    path = Path(project) / "scene-plan.md"
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}

    cards = {}
    header = None
    num_idx = 0
    title_idx = None
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [c.strip() for c in stripped[1:-1].split("|")]
        if header is None:
            if "Title Card" in cells:
                header = cells
                title_idx = cells.index("Title Card")
                num_idx = cells.index("#") if "#" in cells else 0
            continue
        if title_idx is None or title_idx >= len(cells):
            continue
        # Markdown separator row (|---|:---:|...) — every cell is only -, : or space.
        if all(c == "" or set(c) <= set("-: ") for c in cells):
            continue
        try:
            scene_num = int(cells[num_idx])
        except (ValueError, IndexError):
            continue
        cards[scene_num] = cells[title_idx]
    return cards


def _parse_title_card_cell(cell, scene_num):
    """cell: the scene-plan.md `Title Card` column value for one scene.

    Returns None for '—' (no card on this scene). Returns
    {"side", "eyebrow", "title"} for a valid card. Raises CaptionPlanError naming
    the scene and the allowed values for anything else — the side is declared,
    never guessed."""
    cell = cell.strip()
    if cell == "—":
        return None

    allowed = ", ".join(_TITLE_CARD_SIDES)
    if ":" not in cell:
        raise CaptionPlanError(
            f"scene {scene_num}: malformed Title Card cell {cell!r} — expected "
            f"'—', or '<side>: <eyebrow> / <title>' where <side> is one of {allowed}"
        )
    side, _, rest = cell.partition(":")
    side = side.strip()
    if side not in _TITLE_CARD_SIDES:
        raise CaptionPlanError(
            f"scene {scene_num}: unknown Title Card side {side!r} — "
            f"allowed values are {allowed}"
        )
    if "/" not in rest:
        raise CaptionPlanError(
            f"scene {scene_num}: malformed Title Card cell {cell!r} — expected "
            f"'{side}: <eyebrow> / <title>'"
        )
    eyebrow, _, title = rest.partition("/")
    return {"side": side, "eyebrow": eyebrow.strip(), "title": title.strip()}


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


def _contrast_ratio(foreground, background):
    """The WCAG contrast ratio of two hex colours, with no pass/fail threshold baked
    in — burn_subs.check_contrast() always enforces its own 4.5 floor, so it cannot
    answer "does this clear 3:1" for a colour pair that legitimately sits between 3
    and 4.5. Reuses burn_subs._luminance() (the actual WCAG gamma-correction maths);
    only the ratio combination — the two-line formula from the WCAG spec, not a
    re-derivation of the luminance calculation — is repeated here."""
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def check_brand_contrast(brand):
    """Refuse a brand whose caption text would be unreadable before a kinetic-caption
    render is paid for, and decide which token draws readably on the highlight box.

    Two thresholds, not one:
      * ordinary caption text — `ink` on `background` — must clear
        burn_subs.MIN_CONTRAST_RATIO (4.5:1). Enforced via burn_subs.check_contrast(),
        no WCAG maths duplicated for this pairing.
      * the highlight box's own text — whichever of `ink` or `background` reads
        better against `accent` — only needs WCAG AA's large-text floor (3:1), since
        caption text here is never smaller than 32px.

    Returns the winning token name ("ink" or "background") so the caller can write it
    into work/caption-plan.json's `style.highlight_text_token`, and the component
    reads that decision instead of making its own. Raises burn_subs.StyleError when
    either threshold is not met."""
    check_contrast(brand["ink"], brand["background"])

    ink_ratio = _contrast_ratio(brand["ink"], brand["accent"])
    background_ratio = _contrast_ratio(brand["background"], brand["accent"])
    if ink_ratio >= background_ratio:
        token, ratio = "ink", ink_ratio
    else:
        token, ratio = "background", background_ratio

    if ratio < HIGHLIGHT_TEXT_MIN_CONTRAST_RATIO:
        raise StyleError(
            f"highlight box text is unreadable against accent {brand['accent']}: "
            f"ink scores {ink_ratio:.2f}:1, background scores {background_ratio:.2f}:1, "
            f"neither reaches {HIGHLIGHT_TEXT_MIN_CONTRAST_RATIO}:1"
        )
    return token


def build_caption_plan(project, style=None, api_key=None, keyterms=None, brand=None,
                        title_cards=None):
    """Read vo/vo-manifest.json + work/audio-plan.json, score highlight spans, and
    return the work/caption-plan.json payload (not yet written to disk — see main()).

    `brand` is the project's brand.json dict, when one exists yet (see _read_brand()).
    When given, check_brand_contrast(brand) runs and its winning token name is written
    into style.highlight_text_token — Captions.template.tsx reads that decision rather
    than making it. When no brand is given (no Remotion workspace scaffolded yet), the
    key is simply absent; nothing is guessed.

    `title_cards` is {scene_num: raw_cell_text} from scene-plan.md's `Title Card`
    column (see _read_scene_plan_title_cards()); when not given it is read from
    `project/scene-plan.md` directly. Every non-'—' cell is validated up front — a
    malformed cell raises even for a scene with no narration/dialogue at all, so a
    typo in scene-plan.md is caught before any caption work is paid for. Every valid
    card, whether or not its scene has captions, is recorded in the plan's top-level
    `title_cards` list (Phase D)."""
    project = Path(project)
    style = {**DEFAULT_STYLE, **(style or {})}
    if brand is not None:
        style["highlight_text_token"] = check_brand_contrast(brand)

    manifest = _read_manifest(project / "vo" / "vo-manifest.json")
    words_by_id = {item["id"]: item.get("words", []) for item in manifest.get("items", [])}

    audio_plan = _read_audio_plan(project / "work" / "audio-plan.json")
    kw = keyterms if keyterms is not None else derive_keyterms(project)

    raw_title_cards = (title_cards if title_cards is not None
                        else _read_scene_plan_title_cards(project))
    cards_by_scene = {}
    title_cards_out = []
    for scene_num, cell in sorted(raw_title_cards.items()):
        card = _parse_title_card_cell(cell, scene_num)
        if card is None:
            continue
        cards_by_scene[scene_num] = card
        title_cards_out.append({"scene": scene_num, **card})

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

            out_words = [{"text": w["text"], "start_ms": w["start_ms"], "end_ms": w["end_ms"]}
                         for w in words]

            scene_record = {
                "scene": scene_num,
                "vo_item_id": item_id,
                "offset_s": offset_s,
                "timing_source": source,
                "words": out_words,
                "highlights": highlights,
            }
            if aligned:
                scene_record["aligned"] = True

            card = cards_by_scene.get(scene_num)
            if card is not None:
                # A title card holds for TITLE_CARD_HOLD_S from the scene's start,
                # clamped to the scene's own length when the scene is shorter. Any
                # caption words that would start inside that window are pushed to
                # its end — a page already running when the card begins (i.e. one
                # whose first word already starts at or after the hold) is left
                # alone. See reference/script-to-scene-bridge.md > "Title Card".
                scene_duration_s = layer.get("dur_s")
                if not scene_duration_s:
                    scene_duration_s = out_words[-1]["end_ms"] / 1000.0
                hold_s = min(TITLE_CARD_HOLD_S, float(scene_duration_s))
                hold_ms = hold_s * 1000.0
                shift_ms = max(0.0, hold_ms - out_words[0]["start_ms"])
                if shift_ms > 0:
                    for w in out_words:
                        w["start_ms"] += shift_ms
                        w["end_ms"] += shift_ms
                scene_record["captions_held_until_s"] = hold_s

            scenes_out.append(scene_record)

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "style": style,
        "scenes": scenes_out,
        "untimed": untimed,
        "title_cards": title_cards_out,
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


def _read_brand(project):
    """The scaffolded Remotion workspace's brand.json, if one exists yet — see
    templates/remotion/scaffold.mjs, which writes it to shots/src/shots/brand.json.
    Kinetic captions don't require an explainer shot to already exist in the project,
    so a missing file is a normal case, not an error: build_caption_plan() simply
    leaves style.highlight_text_token unset rather than guessing a palette."""
    path = Path(project) / "shots" / "src" / "shots" / "brand.json"
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CaptionPlanError(f"{path.name} is not valid JSON: {exc.msg}") from exc


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
        brand = _read_brand(project)
        plan = build_caption_plan(project, api_key=api_key, brand=brand)
    except (CaptionPlanError, StyleError) as exc:
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
