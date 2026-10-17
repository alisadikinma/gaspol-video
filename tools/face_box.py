#!/usr/bin/env python3
"""Face box per sampled frame of a clip, for the layout gate (GV-23).

    python3 tools/face_box.py <video> [--every N] [--out file.json]

Prints (or writes) a JSON list `[{"frame": i, "t": seconds, "box": [x0, y0, x1, y1] | null}]`.
Boxes are pixel ints, end-exclusive like tools/vidkit/layout.safe_box. `null` means no face
was found in that frame; the caller must report it, not count it as a pass. Largest face wins
when several are found.

Exit 0 written. Exit 2 the model file is missing (run tools/setup.sh), a venv module is
missing, or the video is unreadable. The model is MediaPipe's BlazeFace short-range detector.
This module imports on bare python3; mediapipe loads only inside make_detector.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


class ModelMissing(Exception):
    """The face detector model file is not on disk."""


class VideoUnreadable(Exception):
    """The file has no readable video stream or no frames."""


def frame_indices(total, every_n):
    if every_n < 1:
        raise ValueError(f"--every must be >= 1, got {every_n}")
    return list(range(0, total, every_n))


def to_pixel_box(x, y, w, h, frame_w, frame_h, relative=False):
    """Origin+size to [x0, y0, x1, y1] pixel ints, clamped to the frame, end-exclusive."""
    if relative:
        x, y, w, h = x * frame_w, y * frame_h, w * frame_w, h * frame_h
    x0 = max(0, round(x))
    y0 = max(0, round(y))
    x1 = min(frame_w, round(x + w))
    y1 = min(frame_h, round(y + h))
    return [int(x0), int(y0), int(x1), int(y1)]


def record(index, fps, box):
    return {"frame": index, "t": round(index / fps, 3), "box": box}


def probe(video):
    """(width, height, fps, frame count); frames 0 when the file holds no video."""
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=width,height,r_frame_rate,nb_read_packets",
         "-of", "json", str(video)],
        capture_output=True, text=True)
    try:
        stream = json.loads(proc.stdout)["streams"][0]
        num, _, den = stream["r_frame_rate"].partition("/")
        fps = float(num) / float(den or 1)
        return int(stream["width"]), int(stream["height"]), fps, int(stream["nb_read_packets"])
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return 0, 0, 0.0, 0


def read_frames(video, w, h):
    """Raw RGB bytes, one frame at a time, straight off an ffmpeg pipe."""
    size = w * h * 3
    proc = subprocess.Popen(
        [FFMPEG, "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
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


def boxes(video, every_n, detect):
    """Records for every `every_n`-th frame. `detect(rgb, index, w, h)` returns a box or None."""
    w, h, fps, total = probe(video)
    if total == 0 or w == 0 or h == 0:
        raise VideoUnreadable(f"cannot read video: {video}")
    wanted = set(frame_indices(total, every_n))
    out = []
    for i, rgb in enumerate(read_frames(video, w, h)):
        if i in wanted:
            out.append(record(i, fps, detect(rgb, i, w, h)))
    return out


def model_path():
    home = Path(os.environ.get("GASPOL_VIDEO_HOME", str(Path.home() / ".gaspol-video")))
    return home / "models" / "blaze_face_short_range.tflite"


def make_detector():
    path = model_path()
    if not path.is_file():
        raise ModelMissing(f"model missing: {path}; run tools/setup.sh")
    mp = _venv.require("mediapipe")
    np = _venv.require("numpy")
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    detector = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(path), delegate=python.BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.IMAGE))

    def detect(rgb, index, w, h):
        data = np.frombuffer(rgb, dtype=np.uint8).reshape(h, w, 3)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(data))
        found = detector.detect(image).detections
        if not found:
            return None
        # Bounding boxes are absolute pixels (origin_x, origin_y, width, height).
        best = max(found, key=lambda d: d.bounding_box.width * d.bounding_box.height)
        b = best.bounding_box
        return to_pixel_box(b.origin_x, b.origin_y, b.width, b.height, w, h)

    return detect


def main(argv=None):
    ap = argparse.ArgumentParser(description="Face box per sampled frame of a clip.")
    ap.add_argument("video")
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.every < 1:
        print("--every must be >= 1", file=sys.stderr)
        return 2
    try:
        detect = make_detector()
        result = boxes(args.video, args.every, detect)
    except _venv.DependencyMissing as e:
        print(str(e), file=sys.stderr)
        return 2
    except (VideoUnreadable, ModelMissing) as e:
        print(str(e), file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
