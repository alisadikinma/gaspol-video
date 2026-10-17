"""Contact sheets: look at a clip (or several) without watching it."""
from .ff import duration, ensure_parent, ffmpeg


def contact_sheet(clip, out, frames=5, cols=None, width=360, times=None):
    """``frames`` evenly spaced frames of one clip tiled into one JPEG.

    ``times`` (seconds) picks exact frames instead, e.g. the last frame; one tile per time, in
    order, no padding, ``cols`` defaults to one row. A short last row is filled black.
    """
    if times is not None:
        return _sheet_at(clip, out, list(times), cols, width)
    d = duration(clip)
    cols = cols or frames
    rows = -(-frames // cols)
    ensure_parent(out)
    # fps picks one frame per slot; the half-slot offset keeps the first/last off black edges.
    ffmpeg("-i", clip, "-vf",
           f"fps={frames}/{d:.4f},scale={width}:-2,tile={cols}x{rows}:padding=4:color=black",
           "-frames:v", "1", "-q:v", "3", out)
    return out


def _sheet_at(clip, out, times, cols, width):
    if not times:
        raise ValueError("times is empty")
    if any(t < 0 for t in times):
        raise ValueError(f"times must be >= 0, got {times}")
    n = len(times)
    cols = cols or n
    args = []
    for t in times:
        args += ["-ss", f"{t:.4f}", "-i", str(clip)]
    # One input per time, cut to its first frame: an exact seek, no fps resampling.
    tiles = "".join(f"[{k}:v]scale={width}:-2,trim=end_frame=1,setpts=PTS-STARTPTS[s{k}];"
                    for k in range(n))
    if n == 1:
        graph = tiles.rstrip(";").replace("[s0]", "[o]")
    elif cols >= n:
        graph = tiles + "".join(f"[s{k}]" for k in range(n)) + f"hstack=inputs={n}[o]"
    else:
        layout = "|".join(f"{'+'.join(['w0'] * (k % cols)) or '0'}_{'+'.join(['h0'] * (k // cols)) or '0'}"
                          for k in range(n))
        graph = tiles + "".join(f"[s{k}]" for k in range(n)) + f"xstack=inputs={n}:layout={layout}:fill=black[o]"
    ensure_parent(out)
    ffmpeg(*args, "-filter_complex", graph, "-map", "[o]", "-frames:v", "1", "-q:v", "3", out)
    return out


def montage(images, out, cols=2, cell=(540, 960)):
    """Tile existing image files (e.g. one QA frame per scene) into one sheet. Every image is
    scaled to ``cell`` (width, height); a short last row is padded black."""
    images = [str(i) for i in images]
    if not images:
        raise ValueError("no images")
    w, h = cell
    args = []
    for i in images:
        args += ["-i", i]
    n = len(images)
    scaled = "".join(f"[{k}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[s{k}];" for k in range(n))
    layout = "|".join(f"{(k % cols) * w}_{(k // cols) * h}" for k in range(n))
    graph = scaled + "".join(f"[s{k}]" for k in range(n)) + f"xstack=inputs={n}:layout={layout}:fill=black[o]"
    if n == 1:
        graph = scaled.rstrip(";").replace("[s0]", "[o]")
    ensure_parent(out)
    ffmpeg(*args, "-filter_complex", graph, "-map", "[o]", "-frames:v", "1", "-q:v", "3", out)
    return out
