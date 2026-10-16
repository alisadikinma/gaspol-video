"""Contact sheets: look at a clip (or several) without watching it."""
from .ff import duration, ensure_parent, ffmpeg


def contact_sheet(clip, out, frames=5, cols=None, width=360):
    """``frames`` evenly spaced frames of one clip tiled into one JPEG."""
    d = duration(clip)
    cols = cols or frames
    rows = -(-frames // cols)
    ensure_parent(out)
    # fps picks one frame per slot; the half-slot offset keeps the first/last off black edges.
    ffmpeg("-i", clip, "-vf",
           f"fps={frames}/{d:.4f},scale={width}:-2,tile={cols}x{rows}:padding=4:color=black",
           "-frames:v", "1", "-q:v", "3", out)
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
