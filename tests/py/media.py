"""Synthesize tiny test clips with ffmpeg.

No binary fixtures are committed. Everything the media tests need is generated at run
time from ffmpeg's own lavfi sources, which keeps the repo free of sample files and
means the fixtures cannot rot out of sync with the ffmpeg actually installed.
"""

import shutil
import subprocess
import unittest

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

requires_ffmpeg = unittest.skipUnless(
    FFMPEG and FFPROBE, "ffmpeg/ffprobe not on PATH"
)


def _run(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{proc.stderr[-800:]}")


def make_clip(path, seconds=2.0, fps=30, size="320x240", audio=True, audio_seconds=None):
    """A clip with colour bars and, unless audio=False, a sine tone.

    audio_seconds shorter than seconds produces the A/V mismatch the probe must flag.
    """
    args = [FFMPEG, "-y", "-v", "error",
            "-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i",
                 f"sine=frequency=440:duration={audio_seconds if audio_seconds else seconds}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds)]
    # No -shortest: the output -t caps the video, and a shorter audio input simply ends
    # early. That is exactly the A/V mismatch the probe has to notice.
    args += ["-c:a", "aac"] if audio else ["-an"]
    args.append(str(path))
    _run(args)
    return str(path)


def make_silent_clip(path, seconds=2.0, fps=30, size="320x240"):
    return make_clip(path, seconds=seconds, fps=fps, size=size, audio=False)


def duration_of(path, stream="v:0"):
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    out = proc.stdout.strip().splitlines()
    if not out or out[0] in ("", "N/A"):
        return None
    return float(out[0])
