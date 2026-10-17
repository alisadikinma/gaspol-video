"""Take someone else's video from a link and cut it into scenes with reference frames.

Used by the repackage workflow (skills/video-repackage). Download is yt-dlp; the scene cut is
ffmpeg's scene-change score. Nothing here is specific to one video: every threshold is an argument.
"""
import json
import re
from pathlib import Path

from . import ff


def download(url, out_dir, name="source", cookies_from_browser=None):
    """Download `url` with yt-dlp as `<out_dir>/<name>.mp4` (best mp4, audio kept). Returns the path.

    `cookies_from_browser` (e.g. "chrome") lets yt-dlp read that browser's login cookies; Instagram
    reels refuse anonymous downloads ("login required"). The cookies are read, never written to disk.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.mp4"
    cookies = ["--cookies-from-browser", cookies_from_browser] if cookies_from_browser else []
    ff.run(["yt-dlp", "--no-playlist", *cookies, "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "--merge-output-format", "mp4", "-o", str(target), url])
    if not target.exists():
        raise ff.FFError(f"yt-dlp finished but {target} does not exist")
    return target


def scenes_from_cuts(cuts, duration, min_len=0.6):
    """Cut times (seconds) -> [(start, end)] covering 0..duration.

    A cut that would leave a scene shorter than `min_len` is dropped (flash frames and
    transition frames are not scenes). The last scene is stretched to `duration`.
    """
    if duration <= 0:
        raise ValueError("duration must be positive")
    points = [0.0]
    for c in sorted(cuts):
        if c - points[-1] >= min_len and duration - c >= min_len:
            points.append(float(c))
    points.append(float(duration))
    return [(round(a, 3), round(b, 3)) for a, b in zip(points, points[1:])]


def detect_cuts(video, threshold=0.3):
    """Times where ffmpeg's scene score passes `threshold` (0.2 = sensitive, 0.5 = hard cuts only)."""
    err = ff.run(["ffmpeg", "-v", "info", "-i", video, "-vf",
                  f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"],
                 capture_stderr=True)
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", err)]


def split_scenes(video, out_dir, threshold=0.3, min_len=0.6):
    """Cut `video` into scenes. For each scene writes `scene-NN.mp4` and three stills
    (`scene-NN-first.png`, `-mid.png`, `-last.png`), plus `scenes.json`. Returns the list.

    The mid frame is the usual image reference for regenerating the scene; first and last
    frames help when the scene moves a lot.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = ff.probe(video)["duration"]
    scenes = scenes_from_cuts(detect_cuts(video, threshold), dur, min_len)
    rows = []
    for i, (a, b) in enumerate(scenes, 1):
        n = f"scene-{i:02d}"
        ff.ffmpeg("-ss", a, "-to", b, "-i", video, "-c:v", "libx264", "-crf", "18", "-c:a", "aac", out_dir / f"{n}.mp4")
        for tag, t in (("first", a), ("mid", (a + b) / 2), ("last", max(a, b - 0.05))):
            ff.ffmpeg("-ss", t, "-i", video, "-frames:v", 1, out_dir / f"{n}-{tag}.png")
        rows.append({"scene": i, "start": a, "end": b, "length": round(b - a, 3),
                     "clip": f"{n}.mp4", "first": f"{n}-first.png", "mid": f"{n}-mid.png", "last": f"{n}-last.png"})
    (out_dir / "scenes.json").write_text(json.dumps({"source": str(video), "duration": dur, "scenes": rows}, indent=1))
    return rows
