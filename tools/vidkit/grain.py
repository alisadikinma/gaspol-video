"""Add fine film grain so generated footage stops looking airbrushed.

Video models render skin and backgrounds too clean: no sensor noise, so faces read as plastic next
to real camera footage. Temporal (moving) noise, the same kind a camera makes at night, breaks that
smoothness without changing the face or the motion. Put the same strength on every clip of a film
so generated shots and real footage look like one camera. Strength 6-8 is subtle on a phone; 14 is
clearly visible (use it only to show the effect).
"""
from pathlib import Path

from . import ff


def vf(strength=7):
    """ffmpeg video filter for grain of `strength` (1-40). `allf=t` = new noise every frame."""
    if not 0 < strength <= 40:
        raise ValueError(f"strength must be in 1..40, got {strength}")
    return f"noise=alls={strength}:allf=t"


def apply(src, out, strength=7, crf=16):
    """Write `out` = `src` with grain; audio copied untouched. Returns `out`."""
    if Path(src).resolve() == Path(out).resolve():
        raise ValueError("out must differ from src (an approved clip is never overwritten)")
    ff.ffmpeg("-i", src, "-vf", vf(strength), "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p",
              "-c:a", "copy", out)
    return out
