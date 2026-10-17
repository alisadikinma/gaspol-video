#!/usr/bin/env python3
"""Layout gate for 9:16 short video (GV-23): text must sit inside the measured safe area
and clear of the speaker's face.

    python3 tools/layout_gate.py check <project> [--video output/final.mp4] [--ass FILE]
            [--thumb GLOB] [--overlay SHOTS_DIR|PROJECT|OVERLAY_JSON] [--profile short-organic]
            [--every 15]

Paths are read relative to <project> (a path that exists as given is used as given).
Needs --ass, --thumb and/or --overlay; --video adds the face check of the subtitles.

--overlay (kinetic overlay text, GV-23): for each `overlay-<scene>.json` of the Remotion workspace,
the cue text is rendered ALONE on flat mid-grey by `scripts/render-overlay-text.mjs` (the real
KineticOverlay in `textOnly` mode, at the frame where each cue is at full size), its box is measured
like a subtitle, and checked against the safe area and against the face boxes of the scene clip
sampled while the cue is on screen. Needs the workspace's `npm install` (Remotion + Chrome); if the
render cannot run the gate exits 2 with the reason and never estimates a width. An overlay that is
not 9:16 is noted and skipped. Stills go to `<project>/.tmp/overlay-text/`, one preview per scene
and platform to `<project>/.tmp/layout-overlay-<scene>-{tiktok,reels,shorts}.jpg`. Overlay text
fails only by touching the face; the subtitle chin gap does not apply.

Exit 0: no finding. Exit 1: at least one finding. Exit 2: bad input (missing file, unknown
profile, not 9:16, thumbnail without `<thumb>.box.json`, missing face model or venv).
The report goes to stdout and `<project>/work/layout-report.md`; one preview per platform to
`<project>/.tmp/layout-{tiktok,reels,shorts}.jpg`. Face samples with no face are listed under
"Skipped", never counted as a pass.

Boxes are pixel ints [x0, y0, x1, y1], end-exclusive, like tools/vidkit/layout.safe_box and
layout.text_box. Subtitle and watermark boxes are measured, not computed: the ASS event is
rendered alone on a black canvas with ffmpeg and the non-black extent is read back. The
profile is scaled to the video's display size, so a 576x1024 clip is checked at 576x1024;
anything that is not 9:16 is refused.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv, face_box  # noqa: E402
from tools.vidkit import ff, layout  # noqa: E402

WATERMARK_RE = re.compile(r"\\an5\\pos\(")
EDGE_ORDER = ("left", "top", "right", "bottom")


class InputError(Exception):
    """Bad input: the tool cannot run (exit 2)."""


def _clock_seconds(text):
    h, m, s = text.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _split_ass(ass_text):
    """(header lines, [(start_s, end_s, line)]) of the Dialogue events."""
    header, events = [], []
    for line in ass_text.splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            events.append((_clock_seconds(fields[1]), _clock_seconds(fields[2]), line))
        else:
            header.append(line)
    return header, events


def is_watermark(line):
    return bool(WATERMARK_RE.search(line))


def subtitle_times(ass_text):
    """Midpoint of every subtitle event (watermark excluded), in file order."""
    _, events = _split_ass(ass_text)
    return [round((s + e) / 2, 3) for s, e, line in events if not is_watermark(line)]


def play_res(ass_text):
    """(PlayResX, PlayResY) from an ASS header, or None."""
    x = re.search(r"^PlayResX:\s*(\d+)", ass_text, re.M)
    y = re.search(r"^PlayResY:\s*(\d+)", ass_text, re.M)
    return (int(x.group(1)), int(y.group(1))) if x and y else None


def _render_box(ass_lines, t, size, tmp, background="0x808080"):
    """Render the given ASS lines alone on `background` at time t; return the text box or None.

    Mid-grey by default so a black outline and shadow differ from the canvas and count in
    the box. A near-transparent white line (the watermark) needs "black": on grey its
    contrast is below the detection threshold."""
    w, h = size
    ass_path = os.path.join(tmp, "only.ass")
    Path(ass_path).write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    png = os.path.join(tmp, "frame.png")
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color={background}:s={w}x{h}:r=25:d={t + 2:.3f}",
            "-vf", f"ass=filename={_filter_path(ass_path)}", "-ss", f"{t:.3f}", "-frames:v", "1", png])
    return layout.text_box(png, background=0 if background == "black" else 0x80)


def _filter_path(path):
    return "'" + str(path).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:") + "'"


def _only(ass_text, want_watermark):
    header, events = _split_ass(ass_text)
    return header + [line for _, _, line in events if is_watermark(line) == want_watermark]


def _size_for(ass_text, size):
    if size is not None:
        return size
    return play_res(ass_text) or (1080, 1920)


def text_boxes_from_ass(ass_path, times=None, size=None):
    """[{"t", "box"}] for the subtitle events (watermark left out).

    `times` defaults to the midpoint of each subtitle event. `box` is None when nothing is
    drawn at that time. `size` is the canvas (w, h); default the ASS PlayRes.
    """
    ass_text = Path(ass_path).read_text(encoding="utf-8")
    if times is None:
        times = subtitle_times(ass_text)
    size = _size_for(ass_text, size)
    lines = _only(ass_text, want_watermark=False)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for t in times:
            out.append({"t": t, "box": _render_box(lines, t, size, tmp)})
    return out


def watermark_box(ass_path, size=None):
    """Box of the watermark event, measured the same way. None when the ASS has none."""
    ass_text = Path(ass_path).read_text(encoding="utf-8")
    header, events = _split_ass(ass_text)
    marks = [(s, e, line) for s, e, line in events if is_watermark(line)]
    if not marks:
        return None
    s, e, _ = marks[0]
    lines = _only(ass_text, want_watermark=True)
    with tempfile.TemporaryDirectory() as tmp:
        return _render_box(lines, round((s + e) / 2, 3), _size_for(ass_text, size), tmp, background="black")


def title_source(thumb_path):
    """Absolute path of the clean image the title was stamped on, when `vidkit title` recorded
    it and the file is still readable; else None."""
    try:
        src = json.loads(Path(str(thumb_path) + ".box.json").read_text()).get("source")
    except (OSError, ValueError):
        return None
    return src if src and Path(src).is_file() else None


def title_box(thumb_path):
    """Box written by `vidkit title` next to the thumbnail (<thumb>.box.json)."""
    box_file = Path(str(thumb_path) + ".box.json")
    if not box_file.is_file():
        raise InputError(f"{box_file} missing: stamp the title with `python3 -m tools.vidkit title` "
                         "so the gate can read its box")
    try:
        return json.loads(box_file.read_text())["box"]
    except (ValueError, KeyError) as e:
        raise InputError(f"{box_file}: unreadable ({e})") from e


def check_safe(boxes, profile):
    """Findings for boxes that leave the safe area, one per overflowed edge.

    `boxes` is [{"what", "t", "box"}]; a box of None is skipped (nothing drawn). Findings are
    {"what", "t", "box", "overflow_px", "edge"}.
    """
    sx0, sy0, sx1, sy1 = layout.safe_box(profile)
    found = []
    for b in boxes:
        box = b["box"]
        if box is None:
            continue
        over = {"left": sx0 - box[0], "top": sy0 - box[1],
                "right": box[2] - sx1, "bottom": box[3] - sy1}
        for edge in EDGE_ORDER:
            if over[edge] > 0:
                found.append({"what": b["what"], "t": b["t"], "box": box,
                              "overflow_px": over[edge], "edge": edge})
    return found


# ------------------------------------------------------------------ face checks

def _intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_face(sub_boxes, face_boxes, profile):
    """(findings, skipped) for subtitle boxes against the face box nearest in time.

    `sub_boxes` is [{"what", "t", "box"}], `face_boxes` the records of tools/face_box.py.
    A subtitle that intersects the face is "overlaps face"; one that starts less than
    chin_gap_pct * height below the face box bottom is "too close under the face"; one wholly
    above the face is fine. A matched sample with no face goes to `skipped`, never to a pass.
    """
    min_gap = round(layout.value(profile, "subtitle.chin_gap_pct") * profile["height"])
    findings, skipped, seen = [], [], set()
    for sub in sub_boxes:
        box = sub["box"]
        if box is None or not face_boxes:
            continue
        rec = min(face_boxes, key=lambda r: abs(r["t"] - sub["t"]))
        face = rec["box"]
        if face is None:
            if rec["frame"] not in seen:
                seen.add(rec["frame"])
                skipped.append({"frame": rec["frame"], "t": rec["t"], "reason": "no face detected"})
            continue
        if _intersects(box, face):
            findings.append({"what": sub["what"], "t": sub["t"], "box": box, "face": face,
                             "kind": "overlaps face"})
        elif box[1] >= face[3] and box[1] - face[3] < min_gap:
            findings.append({"what": sub["what"], "t": sub["t"], "box": box, "face": face,
                             "kind": "too close under the face", "gap_px": box[1] - face[3],
                             "min_gap_px": min_gap})
    return findings, skipped


def check_title_face(title, face):
    """Findings when the thumbnail title box touches the face box of the cover image."""
    if title is None or face is None or not _intersects(title, face):
        return []
    return [{"what": "title", "t": None, "box": title, "face": face, "kind": "title overlaps face"}]


# ------------------------------------------------------------------ overlay text (GV-23)

RENDER_SCRIPT = "scripts/render-overlay-text.mjs"
OVERLAY_GREY = 0x80  # the flat background of KineticOverlay textOnly


def find_overlays(target):
    """(shots workspace dir, [overlay json paths]) for a workspace dir, a project dir that holds
    `shots/`, or one overlay json."""
    t = Path(target)
    if not t.exists():
        raise InputError(f"overlay path not found: {t}")
    if t.is_file():
        return str(t.parent.parent.parent), [str(t)]
    if (t / "src" / "shots").is_dir():
        shots = t
    elif (t / "shots" / "src" / "shots").is_dir():
        shots = t / "shots"
    else:
        raise InputError(f"{t}: no Remotion workspace (src/shots/) here: scaffold it with "
                         "node templates/remotion/scaffold.mjs <project> and run tools/overlay_plan.py")
    plans = sorted(str(p) for p in (shots / "src" / "shots").glob("overlay-*.json"))
    if not plans:
        raise InputError(f"{shots}: no src/shots/overlay-*.json: run tools/overlay_plan.py first")
    return str(shots), plans


def render_overlay_text(shots_dir, plan_path, out_dir):
    """Render the text-only stills of one overlay json with the workspace's Remotion.
    Returns [{"id", "frame", "inF", "outF", "png"}], one per cue. Raises InputError with the
    reason when it cannot run; nothing is estimated."""
    script = Path(shots_dir) / RENDER_SCRIPT
    if not script.is_file():
        raise InputError(f"{script} missing: re-run node templates/remotion/scaffold.mjs "
                         "on the project to refresh the workspace scripts")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    try:
        done = subprocess.run(["node", RENDER_SCRIPT, str(Path(plan_path).resolve()),
                               "--out", str(Path(out_dir).resolve())],
                              cwd=str(shots_dir), capture_output=True, text=True)
    except FileNotFoundError as e:
        raise InputError(f"cannot render the overlay text: node not found ({e})") from e
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
        raise InputError("cannot render the overlay text (Remotion): " + " | ".join(tail)
                         + f" -- run `npm install` in {shots_dir} if packages are missing")
    plan = json.loads(Path(plan_path).read_text())
    manifest = Path(out_dir) / f"overlay-{plan['scene']}.frames.json"
    try:
        return json.loads(manifest.read_text())
    except (OSError, ValueError) as e:
        raise InputError(f"{manifest}: not written by the render ({e})") from e


def overlay_text_boxes(plan, rendered):
    """[{"what", "t", "box", "cue", "window"}] from the text-only stills of one overlay.

    `plan` is the overlay json; `rendered` the records of render_overlay_text. `box` is None
    when the cue drew nothing. t is the measured frame in seconds; window is the cue's
    (in, out) in seconds."""
    out = []
    for rec in rendered:
        out.append({"what": f"overlay {plan['scene']}/{rec['id']}", "t": round(rec["frame"] / plan["fps"], 3),
                    "box": layout.text_box(rec["png"], background=OVERLAY_GREY), "cue": rec["id"],
                    "window": (rec["inF"] / plan["fps"], rec["outF"] / plan["fps"]), "png": rec["png"]})
    return out


def check_overlay_face(boxes, face_boxes, scale):
    """(findings, skipped) for overlay text boxes against the face boxes sampled while the cue is
    on screen (the nearest sample when none falls inside it). `scale` maps clip pixels to the
    overlay's size. Touching the face is the only failure: there is no chin gap for overlays."""
    findings, skipped, seen = [], [], set()
    for b in boxes:
        if b["box"] is None or not face_boxes:
            continue
        t0, t1 = b["window"]
        recs = [r for r in face_boxes if t0 <= r["t"] <= t1] or \
            [min(face_boxes, key=lambda r: abs(r["t"] - b["t"]))]
        faced = [r for r in recs if r["box"] is not None]
        if not faced:
            key = (b["what"], recs[0]["frame"])
            if key not in seen:
                seen.add(key)
                skipped.append({"frame": recs[0]["frame"], "t": recs[0]["t"],
                                "reason": f"no face detected in the clip while {b['what']} is on screen"})
            continue
        for r in faced:
            face = [round(v * scale) for v in r["box"]]
            if _intersects(b["box"], face):
                findings.append({"what": b["what"], "t": b["t"], "box": b["box"], "face": face,
                                 "kind": "overlaps face"})
                break
    return findings, skipped


# ------------------------------------------------------------------ platform previews

# Each entry gives the UI bands of one platform. "px" values are for a 1080x1920 frame and
# scale with the frame; "pct" values are shares of the frame. Every entry names its source.
PLATFORM_BANDS = {
    # TikTok: bottom 320 px, right 120 px, top 108 px. Third-party (ignitesocialmedia), not an official figure.
    "tiktok": {"px": {"bottom": 320, "right": 120, "top": 108},
               "source": "third-party: ignitesocialmedia TikTok safe zone"},
    # Reels: top 14 %, bottom 35 %, sides 6 %. Official Meta page.
    "reels": {"pct": {"top": 0.14, "bottom": 0.35, "left": 0.06, "right": 0.06},
              "source": "official: Meta, facebook.com/business/help/980593475366490"},
    # Shorts: bottom 400 px, right 192 px. Third-party (createcomfy / aicarousels), not an official figure.
    "shorts": {"px": {"bottom": 400, "right": 192},
               "source": "third-party: createcomfy, aicarousels YouTube Shorts safe zone"},
}
BAND_COLOR = "red@0.35"
SAFE_COLOR = "lime"
BOX_COLOR = "yellow"


def ui_bands(platform, w, h):
    """UI bands of `platform` as (x0, y0, x1, y1) tuples for a w x h frame."""
    spec = PLATFORM_BANDS[platform]
    if "px" in spec:
        v = {k: round(n * h / 1920) for k, n in spec["px"].items() if k in ("top", "bottom")}
        hz = {k: round(n * w / 1080) for k, n in spec["px"].items() if k in ("left", "right")}
    else:
        v = {k: round(n * h) for k, n in spec["pct"].items() if k in ("top", "bottom")}
        hz = {k: round(n * w) for k, n in spec["pct"].items() if k in ("left", "right")}
    bands = []
    if "top" in v:
        bands.append((0, 0, w, v["top"]))
    if "bottom" in v:
        bands.append((0, h - v["bottom"], w, h))
    if "left" in hz:
        bands.append((0, 0, hz["left"], h))
    if "right" in hz:
        bands.append((w - hz["right"], 0, w, h))
    return bands


def _drawbox(box, color, thickness):
    x0, y0, x1, y1 = box
    return f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color={color}:t={thickness}"


def write_preview(out, platform, source, size, safe, ass=None, t=0.0, boxes=()):
    """One JPG: a frame with the platform's UI bands (red), the safe box (green) and the
    measured text boxes (yellow). `source` is a ("video"|"image", path) or None for black."""
    w, h = size
    cmd = ["ffmpeg", "-y", "-v", "error"]
    seek = []
    if source and source[0] == "video":
        cmd += ["-i", source[1]]
        seek = ["-ss", f"{t:.3f}"]
    elif source:
        cmd += ["-i", source[1]]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=black:s={w}x{h}:r=25:d={t + 2:.3f}"]
        seek = ["-ss", f"{t:.3f}"]
    chain = []
    if ass and (source is None or source[0] == "video"):
        chain.append(f"ass=filename={_filter_path(ass)}")
    chain += [_drawbox(b, BAND_COLOR, "fill") for b in ui_bands(platform, w, h)]
    chain.append(_drawbox((safe[0], safe[1], safe[2], safe[3]), SAFE_COLOR, 3))
    chain += [_drawbox(b, BOX_COLOR, 2) for b in boxes if b]
    ff.ensure_parent(out)
    ff.run(cmd + seek + ["-vf", ",".join(chain), "-frames:v", "1", "-pix_fmt", "yuvj420p",
                         "-q:v", "3", str(out)])


# ------------------------------------------------------------------ report and CLI

def _fmt(f):
    t = "" if f.get("t") is None else f"{f['t']:.2f}s"
    if "edge" in f:
        kind = f"outside safe area: {f['edge']} by {f['overflow_px']} px"
    elif "gap_px" in f:
        kind = f"{f['kind']} ({f['gap_px']} px, needs {f['min_gap_px']})"
    else:
        kind = f["kind"]
    return f"| {f['what']} | {t} | {kind} | {f['box']} |"


def render_report(result, info):
    tail = f" ({len(info['skipped'])} face sample(s) skipped, see below)" if info["skipped"] else ""
    lines = ["# Layout report", "", f"Result: {result}{tail}", ""]
    lines += [f"- profile: {info['profile']}", f"- frame: {info['size'][0]}x{info['size'][1]}",
              f"- safe box: {list(info['safe'])}"]
    for k in ("video", "ass", "thumbs", "overlays"):
        if info.get(k):
            lines.append(f"- {k}: {info[k]}")
    lines += ["", f"## Findings ({len(info['findings'])})", ""]
    if info["findings"]:
        lines += ["| what | t | finding | box |", "|---|---|---|---|"]
        lines += [_fmt(f) for f in info["findings"]]
    else:
        lines.append("none")
    lines += ["", f"## Skipped face samples ({len(info['skipped'])})", ""]
    lines += [f"- frame {s['frame']} at {s['t']:.2f}s: {s['reason']}" for s in info["skipped"]] or ["none"]
    lines += ["", f"## Overlay text boxes ({len(info['overlay_boxes'])})", ""]
    if info["overlay_boxes"]:
        lines += ["| what | t | box | still |", "|---|---|---|---|"]
        lines += [f"| {o['what']} | {o['t']:.2f}s | {o['box']} | {o['png']} |" for o in info["overlay_boxes"]]
    else:
        lines.append("none")
    lines += ["", "## Notes", ""]
    lines += [f"- {n}" for n in info["notes"]] or ["none"]
    lines += ["", "## Previews", ""]
    lines += [f"- {p}" for p in info["previews"]] or ["none"]
    return "\n".join(lines) + "\n"


def _resolve(proj, p):
    p = Path(p)
    if p.is_absolute() or p.exists():
        return p
    return proj / p


def _need_nine_sixteen(label, w, h):
    if w <= 0 or h <= 0 or abs(w / h - 9 / 16) > 0.01:
        raise InputError(f"{label} is {w}x{h}: the layout gate only checks 9:16")


def run_check(args, detect=None, render=None):
    proj = Path(args.project)
    if not proj.is_dir():
        raise InputError(f"project folder not found: {proj}")
    if args.every < 1:
        raise InputError("--every must be >= 1")
    if not args.ass and not args.thumb and not args.overlay:
        raise InputError("nothing to check: give --ass (subtitles, watermark), --thumb and/or --overlay")
    if args.video and not args.ass:
        raise InputError("--video is used for the subtitle face check: give --ass too")
    try:
        base = layout.load(args.profile)
    except KeyError as e:
        raise InputError(str(e.args[0])) from e
    except ValueError as e:
        raise InputError(str(e)) from e

    info = {"profile": args.profile, "findings": [], "skipped": [], "notes": [], "previews": [],
            "overlay_boxes": []}
    holder = {"detect": detect}

    def detector():
        if holder["detect"] is None:
            try:
                holder["detect"] = face_box.make_detector()
            except (_venv.DependencyMissing, face_box.ModelMissing) as e:
                raise InputError(str(e)) from e
        return holder["detect"]

    video = ass = None
    size = None
    if args.video:
        video = _resolve(proj, args.video)
        if not video.is_file():
            raise InputError(f"video not found: {video}")
        w, h, _, _ = face_box.probe(video)
        if w == 0:
            raise InputError(f"cannot read video: {video}")
        _need_nine_sixteen(str(video), w, h)
        size = (w, h)
        info["video"] = str(video)
    sub_boxes, extra = [], []
    if args.ass:
        ass = _resolve(proj, args.ass)
        if not ass.is_file():
            raise InputError(f"ass not found: {ass}")
        info["ass"] = str(ass)
        ass_text = ass.read_text(encoding="utf-8")
        if size is None:
            size = play_res(ass_text) or (base["width"], base["height"])
            _need_nine_sixteen(str(ass), *size)
        prof = {**base, "width": size[0], "height": size[1]}
        measured = text_boxes_from_ass(str(ass), size=size)
        sub_boxes = [{"what": "subtitle", **m} for m in measured]
        if not sub_boxes:
            info["notes"].append(f"no subtitles found in {ass}: nothing was measured for subtitles")
        empty = sum(1 for m in measured if m["box"] is None)
        if empty:
            info["notes"].append(f"{empty} subtitle sample(s) drew nothing, so they were not checked")
        _, events = _split_ass(ass_text)
        if any(is_watermark(line) for _, _, line in events):
            wb = watermark_box(str(ass), size=size)
            if wb is None:
                info["notes"].append("the watermark drew nothing (opacity too low to measure?), not checked")
            else:
                extra.append({"what": "watermark", "t": None, "box": wb})
        info["findings"] += check_safe(sub_boxes + extra, prof)
        if video and sub_boxes:
            faces = face_box.boxes(str(video), args.every, detector())
            found, skipped = check_face(sub_boxes, faces, prof)
            info["findings"] += found
            info["skipped"] += skipped
        elif not video and sub_boxes:
            info["notes"].append("face check skipped: no --video given")
    thumbs = []
    if args.thumb:
        pattern = args.thumb if os.path.isabs(args.thumb) else str(proj / args.thumb)
        thumbs = sorted(glob.glob(pattern)) or ([str(Path(args.thumb))] if Path(args.thumb).is_file() else [])
        if not thumbs:
            raise InputError(f"no thumbnail matches {args.thumb}")
        info["thumbs"] = ", ".join(thumbs)
        for th in thumbs:
            pic = ff.probe(th)["video"]
            if not pic:
                raise InputError(f"{th}: no picture")
            tsize = (pic["width"], pic["height"])
            _need_nine_sixteen(th, *tsize)
            tbox = title_box(th)
            tprof = {**base, "width": tsize[0], "height": tsize[1]}
            info["findings"] += check_safe([{"what": "title", "t": None, "box": tbox}], tprof)
            clean = title_source(th)
            if clean is None:
                info["notes"].append(f"{Path(th).name}: face checked on stamped image; source missing")
            face_img = clean or th
            recs = face_box.boxes(face_img, 1, detector())
            face = recs[0]["box"] if recs else None
            if face is None:
                info["skipped"].append({"frame": 0, "t": 0.0,
                                        "reason": f"no face detected on {'source of ' if clean else ''}thumbnail {Path(th).name}"})
            info["findings"] += check_title_face(tbox, face)
            if size is None:
                size = tsize
    overlay_runs = []
    if args.overlay:
        shots_dir, plans = find_overlays(_resolve(proj, args.overlay))
        info["overlays"] = ", ".join(plans)
        renderer = render or render_overlay_text
        for plan_path in plans:
            plan = json.loads(Path(plan_path).read_text())
            osize = (plan["width"], plan["height"])
            name = Path(plan_path).name
            if abs(osize[0] / osize[1] - 9 / 16) > 0.01:
                info["notes"].append(f"{name} is {osize[0]}x{osize[1]}, not 9:16: overlay text not checked")
                continue
            rendered = renderer(shots_dir, plan_path, str(proj / ".tmp" / "overlay-text"))
            oprof = {**base, "width": osize[0], "height": osize[1]}
            obox = overlay_text_boxes(plan, rendered)
            for o in obox:
                if o["box"] is None:
                    info["notes"].append(f"{o['what']} drew nothing at t={o['t']:.2f}s, so it was not checked")
            info["overlay_boxes"] += [o for o in obox if o["box"] is not None]
            info["findings"] += check_safe(obox, oprof)
            clip = Path(shots_dir) / "public" / plan["clip"]
            if not clip.is_file():
                raise InputError(f"overlay clip not found: {clip}")
            cw, ch, _, _ = face_box.probe(clip)
            if cw == 0:
                raise InputError(f"cannot read overlay clip: {clip}")
            faces = face_box.boxes(str(clip), args.every, detector())
            found, skipped = check_overlay_face(obox, faces, osize[0] / cw)
            info["findings"] += found
            info["skipped"] += skipped
            overlay_runs.append((plan, obox, str(clip), oprof))
            if size is None:
                size = osize
    if size is None:
        # only a non-9:16 overlay was given: nothing was measured, say so and stop here
        size = (base["width"], base["height"])
    prof = {**base, "width": size[0], "height": size[1]}
    safe = layout.safe_box(prof)
    info["size"], info["safe"] = size, safe

    t_pre = next((f["t"] for f in info["findings"] if f.get("t") is not None),
                 sub_boxes[0]["t"] if sub_boxes else 0.0)
    if video:
        source = ("video", str(video))
    elif thumbs:
        source = ("image", thumbs[0])
    else:
        source = None
    at_t = [b["box"] for b in sub_boxes if b["t"] == t_pre] + [e["box"] for e in extra]
    if ass or thumbs or video:
        for platform in PLATFORM_BANDS:
            out = proj / ".tmp" / f"layout-{platform}.jpg"
            write_preview(out, platform, source, size, safe, ass=str(ass) if ass else None, t=t_pre, boxes=at_t)
            info["previews"].append(str(out))
    for plan, obox, clip, oprof in overlay_runs:
        bad = next((f["t"] for f in info["findings"]
                    if f["what"].startswith(f"overlay {plan['scene']}/")), None)
        t_o = bad if bad is not None else (obox[0]["t"] if obox else 0.0)
        shown = [o["box"] for o in obox if o["box"] and o["window"][0] <= t_o <= o["window"][1]]
        osafe = layout.safe_box(oprof)
        for platform in PLATFORM_BANDS:
            out = proj / ".tmp" / f"layout-overlay-{plan['scene']}-{platform}.jpg"
            write_preview(out, platform, ("video", clip), (plan["width"], plan["height"]), osafe,
                          t=t_o, boxes=shown)
            info["previews"].append(str(out))
    return info


def main(argv=None, detect=None, render=None):
    ap = argparse.ArgumentParser(description="Layout gate for 9:16 video.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Measure text against the safe area and the face.")
    c.add_argument("project")
    c.add_argument("--video")
    c.add_argument("--ass")
    c.add_argument("--thumb", help="thumbnail path or glob, e.g. packaging/thumb-*.png")
    c.add_argument("--overlay", help="Remotion shots workspace (or the project, or one overlay-<scene>.json): "
                                     "measure the kinetic overlay text rendered alone")
    c.add_argument("--profile", default="short-organic")
    c.add_argument("--every", type=int, default=15, help="face sample step in frames")
    args = ap.parse_args(argv)
    try:
        info = run_check(args, detect, render)
    except (InputError, face_box.VideoUnreadable, ff.FFError, _venv.DependencyMissing) as e:
        print(str(e), file=sys.stderr)
        return 2
    result = "FAIL" if info["findings"] else "PASS"
    text = render_report(result, info)
    report = Path(args.project) / "work" / "layout-report.md"
    ff.ensure_parent(report)
    report.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"report: {report}")
    return 1 if info["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
