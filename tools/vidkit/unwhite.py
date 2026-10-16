"""Turn a logo on a white box into a mark that sits on a surface (paint / worn sticker).

Used before blending a logo onto a prop with CSS `mix-blend-mode: multiply`. ffmpeg only.
"""
from . import ff


def unwhite(src, out, scale=3, key_similarity=0.28, key_blend=0.18, soften=1.2):
    """Upscale, key out near-white, soften the edge. Writes a PNG with alpha."""
    ff.ffmpeg("-i", src, "-vf",
              f"scale=iw*{scale}:ih*{scale}:flags=lanczos,format=rgba,"
              f"colorkey=0xFFFFFF:{key_similarity}:{key_blend},gblur=sigma={soften}", out)
    return out
