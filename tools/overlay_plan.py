#!/usr/bin/env python3
"""Resolve kinetic-overlay cues to frames and stage their media for Remotion.

    python3 tools/overlay_plan.py <output_folder> [--scene 03]

Reads `<output_folder>/work/overlay-plan.json` (`{"scenes": [...]}`). Each scene names its clip,
fps and size, one word source, and its cues in spoken order. The word source is exactly one of:

    "vo_layer":   "<id>"     an item of `vo/vo-manifest.json` (word times relative to that layer)
    "words_file": "<path>"   a JSON list [{text,start_ms,end_ms}] relative to the output folder,
                             e.g. recognizer words for platform-native dialogue

A cue's `words` is found as a contiguous run (case and punctuation ignored, first occurrence after
the previous cue's run). in = run start + vo_offset_s - 0.10 (not below 0), keyword = start of the
keyword (or of `key_words`, the spoken tokens for a keyword shown differently) inside the run, out = run end + vo_offset_s + hold_s (default 0.3). Cues may overlap by at
most 0.1 s and must end inside the clip.

GV-19 optional fields: scene `steps` {total 2-9, marks [{n, words}]} (a numeral bar, not counted
toward the text share), scene `preset` ("viral", source: course), cue `vignette` (bool) and cue
`burst` {icon, count 1-30}. An explicit cue field always overrides the preset.

Writes `shots/src/shots/overlay-<scene>.json` (cues with inF / keyF / outF frames and public media
paths) and stages the clip, media and person-mask frames in `shots/public/overlay/<scene>/`
(hard link, copy as fallback). A `behind` layer needs frames from tools/person_mask.py for the same
clip. Re-running gives identical output.

Exit 0 ok, one line per scene. Exit 1 refused; every problem is listed, each as
"scene <s> cue <id>: <problem>". Exit 2 an input file is missing. Stdlib only.
"""

import argparse
import filecmp
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.gen_captions import _align_norm  # noqa: E402
from tools.vidkit import ff  # noqa: E402


ICONS = ("fire", "gavel", "chart", "cloud", "question", "arrow", "circle",
         "warning", "money", "check", "cross", "clock", "lock")
FX_KEYWORD = (1, 2, 3, 4)
COLORS = ("white", "yellow")
LAYERS = ("front", "behind")
ANCHORS = ("top", "left", "right", "center")
KINDS = ("image", "video")
PREFIXES = ("user:", "ref:", "remotion:")
REMOTION_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
# Two-tier caption defaults (GV-19). Course advice (Montserrat 15-18, centred, a cut every 1-3 s),
# not platform data: source: course. An explicit cue field always wins. "yellow" is drawn with the
# project's `highlight` token, so the neon green of the reference is the brand's, not hardcoded.
PRESETS = {
    "viral": {"cue": {"color": "yellow", "fx": 1}, "anchor": "center", "lead_px": 40,
              "key_px": 120, "source": "course"},
}
STEPS_MIN, STEPS_MAX = 2, 9
BURST_MIN, BURST_MAX = 1, 30
LEAD_S = 0.10
HOLD_DEFAULT_S = 0.3
OVERLAP_MAX_S = 0.1
# Keywords, not subtitles: text may be on screen for at most this share of a scene's speech.
TEXT_SHARE_MAX = 0.5
MASK_STAMP = "source.json"
SCAFFOLD_HINT = ("scaffold the Remotion workspace first: "
                 "node templates/remotion/scaffold.mjs <project>")


class OverlayPlanError(Exception):
    """The plan is refused; `problems` holds every line."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


class MissingInput(Exception):
    """An input file the plan points at does not exist."""


def _load_json(path, what):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise MissingInput(f"{what} not found: {path}")
    except ValueError as e:
        raise OverlayPlanError([f"{what} is not valid JSON ({path}): {e}"])


def resolve_anchor(words, phrase, start_index=0):
    """Index of the first contiguous run of `phrase` in `words` at or after `start_index`.

    Returns (first, last) word indexes, or None. Matching ignores case and edge punctuation."""
    want = [_align_norm(t) for t in phrase.split()]
    want = [t for t in want if t]
    if not want:
        return None
    have = [_align_norm(w["text"]) for w in words]
    for i in range(start_index, len(have) - len(want) + 1):
        if have[i:i + len(want)] == want:
            return i, i + len(want) - 1
    return None


def _find_keyword(words, run, keyword):
    want = [t for t in (_align_norm(x) for x in keyword.split()) if t]
    if not want:
        return None
    have = [_align_norm(w["text"]) for w in words]
    first, last = run
    for i in range(first, last - len(want) + 2):
        if have[i:i + len(want)] == want:
            return i
    return None


def _clip_duration(clip):
    try:
        return ff.probe(clip)["duration"]
    except ff.FFError:
        return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _mask_frames(out, scene, clip_path):
    """Sorted mask png paths when the scene's mask matches its clip, else None."""
    d = Path(out) / ".tmp" / f"mask-{scene}"
    try:
        stamp = json.loads((d / MASK_STAMP).read_text())
        pngs = sorted(p for p in d.glob("*.png") if p.stem.isdigit())
        if stamp["clip_sha256"] == _sha256(clip_path) and len(pngs) == stamp["frames"] \
                and pngs:
            return pngs
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _resolve_src(out, src, label, problems, files):
    """Public path (or {"remotion": name}) for a cue media `src`; collects problems."""
    if not isinstance(src, str) or not src.startswith(PREFIXES):
        problems.append(f"{label}: src prefix must be one of {', '.join(PREFIXES)} (got {src!r})")
        return src
    if src.startswith("remotion:"):
        name = src[len("remotion:"):]
        if not REMOTION_NAME.match(name):
            problems.append(f"{label}: remotion name {name!r} must match ^[A-Z][A-Za-z0-9]*$")
        return {"remotion": name}
    if src.startswith("ref:"):
        path = Path(out) / "ref" / src[len("ref:"):]
    else:
        path = Path(out) / src[len("user:"):]
    if not path.is_file():
        problems.append(f"{label}: media file not found: {path}")
        return src
    files.append(path)
    return path  # replaced by the public path once the scene name is known


def _validate_cue_fields(cue, label, problems):
    fx = cue.get("fx", 1)
    if fx not in FX_KEYWORD:
        problems.append(f"{label}: fx {fx!r} not allowed on a keyword (allowed 1-4; "
                        f"5 and 6 are applied automatically)")
    if cue.get("color", "white") not in COLORS:
        problems.append(f"{label}: color {cue.get('color')!r} not in {list(COLORS)}")
    if cue.get("layer", "front") not in LAYERS:
        problems.append(f"{label}: layer {cue.get('layer')!r} not in {list(LAYERS)}")
    anchor = (cue.get("pos") or {}).get("anchor", "top")
    if anchor not in ANCHORS:
        problems.append(f"{label}: pos anchor {anchor!r} not in {list(ANCHORS)}")
    if cue.get("icon") is not None and cue["icon"] not in ICONS:
        problems.append(f"{label}: icon {cue['icon']!r} not in {list(ICONS)}")
    if fx == 3 and not re.search(r"\d", str(cue.get("keyword", ""))):
        problems.append(f"{label}: fx 3 needs a digit in keyword")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _validate_viral_fields(cue, label, problems):
    if "vignette" in cue and not isinstance(cue["vignette"], bool):
        problems.append(f"{label}: vignette must be true or false (got {cue['vignette']!r})")
    if cue.get("burst") is not None:
        burst = cue["burst"]
        if not isinstance(burst, dict):
            problems.append(f"{label}: burst must be {{icon, count}} (got {burst!r})")
            return
        if burst.get("icon") not in ICONS:
            problems.append(f"{label}: burst icon {burst.get('icon')!r} not in {list(ICONS)}")
        count = burst.get("count")
        if not _is_int(count) or not BURST_MIN <= count <= BURST_MAX:
            problems.append(f"{label}: burst count must be an integer {BURST_MIN}-{BURST_MAX} "
                            f"(got {count!r})")


def _resolve_steps(steps, words, offset, fps, scene, problems):
    """Frames for each step mark: {total, marks: [{n, f}]}, or None when refused. Marks are
    resolved in the order given, each after the previous one. Numerals, not words: they do not
    count toward TEXT_SHARE_MAX."""
    head = f"scene {scene} steps"
    if not isinstance(steps, dict):
        problems.append(f"{head}: must be {{total, marks}} (got {steps!r})")
        return None
    start = len(problems)
    total = steps.get("total")
    if not _is_int(total) or not STEPS_MIN <= total <= STEPS_MAX:
        problems.append(f"{head}: total must be an integer {STEPS_MIN}-{STEPS_MAX} (got {total!r})")
    marks = steps.get("marks")
    if not isinstance(marks, list) or not marks:
        problems.append(f"{head}: needs a non-empty marks list")
        return None
    out, seen, idx, last_n = [], set(), 0, 0
    for mark in marks:
        if not isinstance(mark, dict):
            problems.append(f"{head}: each mark must be {{n, words}} (got {mark!r})")
            continue
        n, label = mark.get("n"), f"{head} mark {mark.get('n')}"
        if not _is_int(n) or n < 1 or (_is_int(total) and n > total):
            problems.append(f"{label}: n must be an integer 1-{total} (got {n!r})")
            continue
        if n in seen:
            problems.append(f"{label}: duplicate n")
            continue
        seen.add(n)
        if n < last_n:
            problems.append(f"{label}: n must increase with time (comes after n {last_n})")
            continue
        last_n = n
        if not str(mark.get("words", "")).strip():
            problems.append(f"{label}: missing words")
        elif words is not None:
            run = resolve_anchor(words, mark["words"], idx)
            if run is None:
                problems.append(f"{label}: words {mark['words']!r} not found in the spoken "
                                f"words after the previous mark")
            else:
                idx = run[1] + 1
                out.append({"n": n, "f": round((words[run[0]]["start_ms"] / 1000 + offset) * fps)})
    if len(problems) > start:
        return None
    return {"total": total, "marks": out}


def _plan_scene(out, sc, problems_all):
    """Resolve one scene. Returns (result dict, staging dict) or None when refused."""
    scene = str(sc.get("scene", ""))
    problems = []

    def add(msg, cue=None):
        prefix = f"scene {scene} cue {cue}: " if cue else f"scene {scene}: "
        problems.append(prefix + msg)

    for key in ("scene", "clip", "fps", "width", "height"):
        if key not in sc:
            add(f"missing field {key!r}")
    if problems:
        problems_all.extend(problems)
        return None

    has_layer, has_file = "vo_layer" in sc, "words_file" in sc
    words = None
    if has_layer == has_file:
        add("exactly one of vo_layer or words_file is required")
    elif has_file:
        data = _load_json(Path(out) / sc["words_file"], "words file")
        if not isinstance(data, list):
            add(f"words file {sc['words_file']} must be a JSON list")
        else:
            words = data
    else:
        manifest = _load_json(Path(out) / "vo" / "vo-manifest.json", "VO manifest")
        item = next((i for i in manifest.get("items", []) if i.get("id") == sc["vo_layer"]),
                    None)
        if item is None:
            add(f"vo_layer {sc['vo_layer']!r} not in vo/vo-manifest.json")
        else:
            words = item.get("words") or []

    clip_path = Path(out) / sc["clip"]
    duration = None
    if not clip_path.is_file():
        add(f"clip not found: {clip_path}")
    else:
        duration = _clip_duration(clip_path)
        if duration is None:
            add(f"cannot read the clip duration: {clip_path}")

    cues = sc.get("cues") or []
    if not cues:
        add("no cues")

    preset = None
    if sc.get("preset") is not None:
        preset = PRESETS.get(sc["preset"])
        if preset is None:
            add(f"preset {sc['preset']!r} not in {list(PRESETS)}")

    fps = sc["fps"]
    offset = float(sc.get("vo_offset_s", 0.0))
    files = []          # source Paths in order of first use
    needs_mask = False
    out_cues = []
    prev_end_idx = 0
    prev_out_s = None
    seen_ids = set()
    visible = []        # (in_s, out_s) of every timed cue

    steps_out = None
    if sc.get("steps") is not None:
        steps_out = _resolve_steps(sc["steps"], words, float(sc.get("vo_offset_s", 0.0)),
                                   sc["fps"], scene, problems)

    for cue in cues:
        cid = str(cue.get("id", "?"))
        if cid in seen_ids:
            add("duplicate cue id", cid)
        seen_ids.add(cid)
        label = f"scene {scene} cue {cid}"
        if preset:
            cue = {**preset["cue"], **cue}
            cue["pos"] = {"anchor": preset["anchor"], **(cue.get("pos") or {})}
        local = []
        _validate_cue_fields(cue, label, local)
        _validate_viral_fields(cue, label, local)
        problems.extend(local)
        for field in ("words", "keyword"):
            if not str(cue.get(field, "")).strip():
                add(f"missing {field}", cid)

        timing = None
        if words is not None and cue.get("words") and cue.get("keyword"):
            run = resolve_anchor(words, cue["words"], prev_end_idx)
            if run is None:
                add(f"words {cue['words']!r} not found in the spoken words "
                    f"after the previous cue", cid)
            else:
                # A shown keyword is often not what was said ("1" for "pertama", "221" for
                # "dua ratus dua puluh satu"), so key_words names the spoken tokens to time it on.
                key_field = "key_words" if cue.get("key_words") else "keyword"
                kidx = _find_keyword(words, run, cue[key_field])
                if kidx is None:
                    add(f"{key_field} {cue[key_field]!r} is not inside words {cue['words']!r}", cid)
                else:
                    prev_end_idx = run[1] + 1
                    hold = float(cue.get("hold_s", HOLD_DEFAULT_S))
                    in_s = max(0.0, words[run[0]]["start_ms"] / 1000 + offset - LEAD_S)
                    key_s = words[kidx]["start_ms"] / 1000 + offset
                    out_s = words[run[1]]["end_ms"] / 1000 + offset + hold
                    timing = (in_s, key_s, out_s)
        if timing:
            in_s, key_s, out_s = timing
            if prev_out_s is not None and prev_out_s - in_s > OVERLAP_MAX_S + 1e-9:
                add(f"overlaps the previous cue by {prev_out_s - in_s:.2f}s "
                    f"(max {OVERLAP_MAX_S}s)", cid)
            if duration is not None and out_s > duration + 1e-9:
                add(f"ends at {out_s:.2f}s, past the clip length {duration:.2f}s", cid)
            prev_out_s = out_s
            visible.append((in_s, out_s))

        # Write every default the composition reads. It matches layer exactly and reads pos.x,
        # so a cue that validated as "front" by default was otherwise silently never drawn.
        entry = dict(cue)
        entry.setdefault("fx", 1)
        entry.setdefault("color", "white")
        entry.setdefault("script", False)
        entry.setdefault("layer", "front")
        entry.setdefault("icon", None)
        entry.setdefault("vignette", False)
        entry.setdefault("burst", None)
        entry.setdefault("source", "")
        pos = dict(cue.get("pos") or {})
        entry["pos"] = {"anchor": pos.get("anchor", "top"), "x": pos.get("x"), "y": pos.get("y")}
        if timing:
            entry["inF"], entry["keyF"], entry["outF"] = (round(t * fps) for t in timing)

        if cue.get("layer", "front") == "behind":
            needs_mask = True
        for group, default_kind in (("panels", "image"), ("bubbles", None), ("carousel", None)):
            items = []
            for item in cue.get(group) or []:
                item = dict(item)
                if group == "panels":
                    item.setdefault("kind", "image")
                    item.setdefault("layer", "front")
                    item.setdefault("caption", "")
                what = f"{group[:-1] if group != 'carousel' else 'carousel item'}"
                sub = []
                if default_kind and item.get("kind", default_kind) not in KINDS:
                    sub.append(f"{label}: {what} kind {item.get('kind')!r} not in {list(KINDS)}")
                if item.get("layer", "front") not in LAYERS:
                    sub.append(f"{label}: {what} layer {item.get('layer')!r} not in "
                               f"{list(LAYERS)}")
                if item.get("layer") == "behind":
                    needs_mask = True
                item["src"] = _resolve_src(out, item.get("src"), f"{label}: {what}", sub, files)
                problems.extend(sub)
                items.append(item)
            # Always present, even empty: the composition maps over all three lists.
            entry[group] = items
        out_cues.append(entry)

    if words and visible:
        speech_s = (words[-1]["end_ms"] - words[0]["start_ms"]) / 1000
        shown_s, cur = 0.0, None
        for a, b in sorted(visible):
            if cur and a <= cur[1]:
                cur = (cur[0], max(cur[1], b))
            else:
                if cur:
                    shown_s += cur[1] - cur[0]
                cur = (a, b)
        shown_s += cur[1] - cur[0]
        if speech_s > 0 and shown_s / speech_s > TEXT_SHARE_MAX + 1e-9:
            problems.append(
                f"scene {scene}: text is on screen {shown_s:.1f}s of {speech_s:.1f}s of speech "
                f"({shown_s / speech_s:.0%}, max {TEXT_SHARE_MAX:.0%}). These are keywords, not "
                f"subtitles: keep only the words that matter (a number, a contrast, the main "
                f"claim, a danger word) and leave gaps with no text")

    mask_pngs = None
    if needs_mask:
        mask_pngs = _mask_frames(out, scene, clip_path) if clip_path.is_file() else None
        if mask_pngs is None:
            add("a behind layer needs a person mask for this clip: "
                "run tools/person_mask.py first")

    # Public names; two different source files may not share a basename.
    base = f"overlay/{scene}"
    owners = {"clip.mp4": clip_path}
    for path in files:
        name = path.name
        if name in owners and os.path.abspath(owners[name]) != os.path.abspath(path):
            add(f"two different media files share the name {name!r}: "
                f"{owners[name]} and {path}")
        owners.setdefault(name, path)

    def publish(item):
        if isinstance(item["src"], Path):
            item["src"] = f"{base}/{item['src'].name}"

    for entry in out_cues:
        for group in ("panels", "bubbles", "carousel"):
            for item in entry.get(group, []):
                publish(item)

    problems_all.extend(problems)
    if problems:
        return None
    result = {
        "scene": scene, "fps": fps, "width": sc["width"], "height": sc["height"],
        "durationInFrames": round(duration * fps),
        "clip": f"{base}/clip.mp4",
        "mask": f"{base}/mask/" if needs_mask else None,
        "cues": out_cues,
    }
    if steps_out:
        result["steps"] = steps_out
    if preset:
        result["preset"] = {"name": sc["preset"], "source": preset["source"],
                            "lead_px": preset["lead_px"], "key_px": preset["key_px"]}
    staging = {"files": owners, "mask": mask_pngs if needs_mask else None}
    return result, staging


def _place(src, dest):
    """Link (or copy) src to dest unless dest already holds the same bytes."""
    dest = Path(dest)
    if dest.exists():
        if os.path.samefile(src, dest) or filecmp.cmp(src, dest, shallow=False):
            return
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def _stage(out, scene, staging):
    pub = Path(out) / "shots" / "public" / "overlay" / scene
    count = 0
    for name, src in staging["files"].items():
        _place(src, pub / name)
        count += 1
    masks = staging["mask"]
    if masks is not None:
        mdir = pub / "mask"
        keep = {p.name for p in masks}
        if mdir.is_dir():
            for stale in mdir.glob("*.png"):
                if stale.name not in keep:
                    stale.unlink()
        for p in masks:
            _place(p, mdir / p.name)
            count += 1
    return count


def run(output_folder, scene=None):
    """Resolve the plan and stage files. Returns one status line per scene."""
    out = Path(output_folder)
    plan = _load_json(out / "work" / "overlay-plan.json", "overlay plan")
    if not (out / "shots").is_dir():
        raise OverlayPlanError([SCAFFOLD_HINT])
    scenes = plan.get("scenes") or []
    if scene is not None:
        scenes = [s for s in scenes if str(s.get("scene")) == str(scene)]
        if not scenes:
            raise OverlayPlanError([f"scene {scene} is not in work/overlay-plan.json"])
    if not scenes:
        raise OverlayPlanError(["work/overlay-plan.json has no scenes"])

    problems, planned = [], []
    for sc in scenes:
        res = _plan_scene(out, sc, problems)
        if res:
            planned.append(res)
    if problems:
        raise OverlayPlanError(problems)

    lines = []
    shots_dir = out / "shots" / "src" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    for result, staging in planned:
        staged = _stage(out, result["scene"], staging)
        (shots_dir / f"overlay-{result['scene']}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        lines.append(f"overlay {result['scene']}: {len(result['cues'])} cues, "
                     f"{staged} files staged")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("output_folder")
    ap.add_argument("--scene", help="only this scene id, e.g. 03")
    args = ap.parse_args(argv)
    try:
        for line in run(args.output_folder, scene=args.scene):
            print(line)
    except MissingInput as e:
        print(f"missing input: {e}", file=sys.stderr)
        return 2
    except OverlayPlanError as e:
        for line in e.problems:
            print(f"refused: {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
