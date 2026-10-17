"""Cut a 9:16 window out of wide (16:9) footage, panning to follow the subject.

Official product footage is usually 16:9; a short is 9:16. A centre crop loses the car the moment it
moves. Here the owner (or an agent looking at a contact sheet) gives a few keys `t:cx`, where `cx`
is the subject's horizontal centre as a fraction of the frame width; the window pans linearly
between keys and holds before the first and after the last. The window never leaves the frame.
"""
import re
from pathlib import Path

from . import ff

_KEY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$")


def parse_keys(text):
    """"0:0.3,2.5:0.7" -> [(0.0, 0.3), (2.5, 0.7)]. Times strictly increase, cx in 0..1."""
    keys = []
    for part in str(text).split(","):
        m = _KEY.match(part)
        if not m:
            raise ValueError(f"key must be T:CX, got {part!r}")
        t, cx = float(m.group(1)), float(m.group(2))
        if not 0 <= cx <= 1:
            raise ValueError(f"cx must be 0..1, got {cx}")
        if keys and t <= keys[-1][0]:
            raise ValueError("key times must increase")
        keys.append((t, cx))
    return keys


def center_at(keys, t):
    """Subject centre (fraction of width) at time t: linear between keys, held at the ends."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, c0), (t1, c1) in zip(keys, keys[1:]):
        if t < t1:
            return c0 + (c1 - c0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def window(src_w, src_h, zoom=1.0):
    """(w, h) of the 9:16 crop, even numbers. zoom > 1 = tighter (less of the frame)."""
    if zoom < 1:
        raise ValueError("zoom must be >= 1")
    h = int(src_h / zoom) // 2 * 2
    w = int(h * 9 / 16) // 2 * 2
    if w > src_w:
        raise ValueError("source is narrower than a 9:16 window")
    return w, h


def x_expr(keys, src_w, win_w):
    """ffmpeg crop `x` expression (uses t) for the left edge of the window."""
    def cx(i):
        if i == len(keys) - 1:
            return f"{keys[-1][1]}"
        (t0, c0), (t1, c1) = keys[i], keys[i + 1]
        return f"if(lt(t,{t1}),{c0}+({c1}-{c0})*(t-{t0})/({t1}-{t0}),{cx(i + 1)})"
    inner = f"if(lt(t,{keys[0][0]}),{keys[0][1]},{cx(0)})"
    return f"clip(({inner})*{src_w}-{win_w / 2},0,{src_w - win_w})"


def apply(src, out, keys, zoom=1.0, size=(1080, 1920), crf=16):
    """Write `out` = 9:16 reframe of `src` following `keys`, scaled to `size`, audio dropped
    (product footage is used under the narration). Returns {"window", "keys"}."""
    if Path(src).resolve() == Path(out).resolve():
        raise ValueError("out must differ from src")
    v = ff.probe(src)["video"]
    w, h = window(v["width"], v["height"], zoom)
    y = (v["height"] - h) // 2
    vf = f"crop={w}:{h}:'{x_expr(keys, v['width'], w)}':{y},scale={size[0]}:{size[1]}:flags=lanczos,setsar=1"
    ff.ffmpeg("-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p", out)
    return {"window": (w, h), "keys": keys}


def fit(src, out, size=(1080, 1920), blur=40, crf=16):
    """Write `out` = the WHOLE wide frame scaled to the output width, centred over a blurred,
    zoomed copy of itself. For shots where the subject is wider than any 9:16 window (a car
    side-on in close-up): panning would cut it, this keeps all of it. Audio dropped."""
    if Path(src).resolve() == Path(out).resolve():
        raise ValueError("out must differ from src")
    w, h = size
    graph = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
             f"boxblur={blur}[bg];[b]scale={w}:-2:flags=lanczos[fg];"
             f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]")
    ff.ffmpeg("-i", src, "-filter_complex", graph, "-map", "[v]", "-an", "-c:v", "libx264",
              "-crf", crf, "-pix_fmt", "yuv420p", out)
    return out
