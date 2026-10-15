#!/usr/bin/env python3
"""Per-frame person mattes for a clip, used to put overlay graphics behind a speaker.

    python3 tools/person_mask.py <output_folder> <scene> <clip.mp4> [--feather 4] [--max-miss 0.10] [--force]

Writes one 8-bit grayscale PNG per frame (white = person) to
`<output_folder>/.tmp/mask-<scene>/00001.png ...` plus `source.json`, the stamp that says which
clip bytes, model and feather produced them. A matching stamp is a cache hit: the segmenter is
not run and nothing is rewritten, unless `--force`.

Exit 0 masks written or cached. Exit 1 refused: no person in more than `--max-miss` of the frames
(the message gives the ratio and the first 20 missing frame numbers, 1-based), the output folder
does not exist, or the clip has no frames. Exit 2 a venv module or the model file is missing;
run tools/setup.sh.

The segmenter is MediaPipe's selfie segmenter, which is class-agnostic: two people in frame are
both masked. Needs Pillow, numpy and mediapipe (the venv built by tools/setup.sh) plus ffmpeg and
ffprobe. This module imports on bare python3; the heavy modules load only where they are used.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

MIN_PERSON_AREA = 0.005
PERSON_THRESHOLD = 128
STAMP = "source.json"
MISS_LIST_LIMIT = 20


class MaskRefused(Exception):
    """The clip cannot be masked well enough to trust; the message says why."""


def clip_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(clip):
    """(width, height, fps, frame count). Frames are 0 when the file holds no video."""
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=width,height,r_frame_rate,nb_read_packets",
         "-of", "json", str(clip)],
        capture_output=True, text=True)
    try:
        stream = json.loads(proc.stdout)["streams"][0]
        num, _, den = stream["r_frame_rate"].partition("/")
        fps = float(num) / float(den or 1)
        return int(stream["width"]), int(stream["height"]), fps, int(stream["nb_read_packets"])
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return 0, 0, 0.0, 0


def read_frames(clip, w, h):
    """Raw RGB bytes, one frame at a time, straight off an ffmpeg pipe."""
    size = w * h * 3
    proc = subprocess.Popen(
        [FFMPEG, "-v", "error", "-i", str(clip), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield buf
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def build_masks(frames_iter, segment, w, h, feather_px):
    """(masks, miss_frames). A miss still gets an all-black mask so counts line up."""
    PIL = _venv.require("PIL")
    from PIL import Image, ImageFilter

    masks, miss = [], []
    for i, rgb in enumerate(frames_iter):
        mask = segment(rgb, i, w, h)
        if mask is not None:
            person = sum(mask.histogram()[PERSON_THRESHOLD:])
            if person < MIN_PERSON_AREA * w * h:
                mask = None
        if mask is None:
            miss.append(i + 1)
            mask = Image.new("L", (w, h), 0)
        elif feather_px > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(feather_px))
        masks.append(mask)
    return masks, miss


def decide(miss_frames, total, max_miss):
    if total == 0:
        raise MaskRefused("clip has no frames")
    ratio = len(miss_frames) / total
    # Round before comparing: 11/100 is 0.11 only up to float noise, and exactly 10% must pass.
    if round(ratio, 9) > round(max_miss, 9):
        shown = ", ".join(str(n) for n in miss_frames[:MISS_LIST_LIMIT])
        more = "" if len(miss_frames) <= MISS_LIST_LIMIT else ", ..."
        raise MaskRefused(
            f"no person in {len(miss_frames)} of {total} frames ({ratio:.0%}, "
            f"limit {max_miss:.0%}). First missing frames: {shown}{more}")


def _png_count(mask_dir):
    return sum(1 for p in Path(mask_dir).glob("*.png")
               if len(p.stem) == 5 and p.stem.isdigit())


def cache_valid(mask_dir, clip_sha, model_sha, feather_px):
    try:
        stamp = json.loads((Path(mask_dir) / STAMP).read_text())
        return (stamp["clip_sha256"] == clip_sha and stamp["model_sha256"] == model_sha
                and stamp["feather_px"] == feather_px
                and _png_count(mask_dir) == stamp["frames"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def write_masks(mask_dir, masks, stamp):
    mask_dir = Path(mask_dir)
    mask_dir.mkdir(parents=True, exist_ok=True)
    # Drop the old stamp first so a crash anywhere below cannot leave a stamp vouching for
    # a half-written set.
    (mask_dir / STAMP).unlink(missing_ok=True)
    for i, mask in enumerate(masks, 1):
        mask.save(mask_dir / f"{i:05d}.png")
    for p in mask_dir.glob("*.png"):
        if p.stem.isdigit() and int(p.stem) > len(masks):
            p.unlink()
    (mask_dir / STAMP).write_text(json.dumps(stamp, indent=2))


def _count_empty(mask_dir):
    _venv.require("PIL")
    from PIL import Image
    return sum(1 for p in sorted(Path(mask_dir).glob("*.png"))
               if Image.open(p).getextrema()[1] < PERSON_THRESHOLD)


def run(output_folder, scene, clip, segment, model_sha, feather_px=4, max_miss=0.10, force=False):
    out = Path(output_folder)
    if not out.is_dir():
        raise MaskRefused(f"output folder does not exist: {out}")
    w, h, fps, frames = probe(clip)
    if frames == 0:
        raise MaskRefused("clip has no frames")

    mask_dir = out / ".tmp" / f"mask-{scene}"
    sha = clip_sha256(clip)
    if not force and cache_valid(mask_dir, sha, model_sha, feather_px):
        return {"frames": _png_count(mask_dir), "miss": _count_empty(mask_dir),
                "cached": True, "dir": str(mask_dir)}

    masks, miss = build_masks(read_frames(clip, w, h), segment, w, h, feather_px)
    decide(miss, len(masks), max_miss)
    write_masks(mask_dir, masks, {
        "clip_sha256": sha, "frames": len(masks), "fps": fps, "w": w, "h": h,
        "feather_px": feather_px, "model_sha256": model_sha})
    return {"frames": len(masks), "miss": len(miss), "cached": False, "dir": str(mask_dir)}


def model_path():
    home = Path(os.environ.get("GASPOL_VIDEO_HOME", str(Path.home() / ".gaspol-video")))
    return home / "models" / "selfie_segmenter.tflite"


def make_segmenter(fps):
    """(segment, model_sha). The selfie model has one confidence mask and it is the person."""
    path = model_path()
    if not path.is_file():
        print(f"model missing: {path}; run tools/setup.sh", file=sys.stderr)
        raise SystemExit(2)
    mp = _venv.require("mediapipe")
    np = _venv.require("numpy")
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from PIL import Image

    segmenter = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=python.BaseOptions(model_asset_path=str(path)),
        running_mode=vision.RunningMode.VIDEO,
        output_confidence_masks=True))

    def segment(rgb, index, w, h):
        data = np.frombuffer(rgb, dtype=np.uint8).reshape(h, w, 3)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(data))
        result = segmenter.segment_for_video(image, int(index * 1000 / fps))
        if not result.confidence_masks:
            return None
        # numpy_view() is H x W x 1, not H x W.
        person = np.asarray(result.confidence_masks[0].numpy_view(), dtype=np.float32).reshape(h, w)
        return Image.fromarray((person.clip(0.0, 1.0) * 255).astype(np.uint8), "L")

    return segment, clip_sha256(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Per-frame person mattes for a clip.")
    ap.add_argument("output_folder")
    ap.add_argument("scene")
    ap.add_argument("clip")
    ap.add_argument("--feather", type=int, default=4)
    ap.add_argument("--max-miss", type=float, default=0.10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if not Path(args.output_folder).is_dir():
        print(f"output folder does not exist: {args.output_folder}", file=sys.stderr)
        return 1
    started = time.time()
    try:
        _venv.require("PIL")
        w, h, fps, frames = probe(args.clip)
        if frames == 0:
            raise MaskRefused("clip has no frames")
        segment, model_sha = make_segmenter(fps)
        res = run(args.output_folder, args.scene, args.clip, segment, model_sha,
                  feather_px=args.feather, max_miss=args.max_miss, force=args.force)
    except _venv.DependencyMissing as e:
        print(str(e), file=sys.stderr)
        return 2
    except MaskRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    print(f"mask {args.scene}: {res['frames']} frames, {res['miss']} without person "
          f"({'cached' if res['cached'] else 'written'}, {time.time() - started:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
