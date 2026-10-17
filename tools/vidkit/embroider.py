"""Embroider a logo onto clothing: raised satin thread instead of flat ink.

Why this is not part of ``bond.py``: a print is flat ink, so ``bond`` multiplies the logo into the
cloth and the result has no relief of its own. Embroidery is thread stitched on top of the cloth.
It has its own height (a rounded ridge along each stroke, fine ridges from the stitches), its own
surface normal and its own shading, and it has to follow the cloth per point rather than through
one global warp. This module builds the thread surface; later phases add the warp and shading.

Needs ``cv2`` and ``numpy`` (shared venv); imported lazily so vidkit stays importable without them.
"""
import math

MAX_LOGO_WIDTH = 2000      # wider logos are downscaled first
NORMAL_STRENGTH = 2.0      # multiplies the Sobel slope of the height map before normalising
RIDGE_DEPTH = 0.25         # height = dome * (1 - RIDGE_DEPTH + RIDGE_DEPTH * ridge)
ALBEDO_JITTER = 0.06       # per-ridge brightness variation, +-6 %
_JITTER_SEED = 24
_JITTER_TABLE = 4096


def _deps():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("embroider needs cv2 and numpy: run tools/setup.sh and use the venv python") from exc
    return cv2, np


def _local_half_width(dist, cv2, np):
    """Half-width of the stroke each pixel belongs to: the largest distance value within its own
    radius (the widest inscribed circle covering it). Radii are bucketed so a big logo stays fast."""
    out = dist.copy()
    top = float(dist.max())
    radius, previous = 1, 0.0
    while previous < top:
        sel = (dist > previous) & (dist <= radius)
        if sel.any():
            k = 2 * radius + 1
            grown = cv2.dilate(dist, np.ones((k, k), np.uint8))
            out[sel] = grown[sel]
        previous = radius
        radius = max(radius + 1, int(math.ceil(radius * 1.25)))
    return out


def _stitch_angles(dist, mask, labels, count, np, cv2):
    """Dominant stitch direction (radians, per connected component) from the distance gradient.

    Satin stitches run across a stroke, which is the direction the distance field rises. Pixels
    are combined with a doubled-angle sum so opposite gradients on the two sides of a stroke add
    up instead of cancelling. A component with no clear direction (a dot) gets 0.
    """
    smooth = cv2.GaussianBlur(dist, (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    flat = labels.ravel()
    sxx = np.bincount(flat, (gx * gx - gy * gy).ravel(), count)
    sxy = np.bincount(flat, (2 * gx * gy).ravel(), count)
    return 0.5 * np.arctan2(sxy, sxx)


def thread_maps(rgba, stitch_px=3.0, angle_deg=None):
    """Return ``(height, normal, albedo)`` for a satin-stitched version of ``rgba``.

    ``rgba`` is a uint8 ``[h, w, 4]`` image in OpenCV channel order (BGRA, as
    ``cv2.imread(..., cv2.IMREAD_UNCHANGED)`` returns it). A logo wider than 2000 px is
    downscaled to 2000 px wide first, so the returned maps have that smaller size.

    * ``height`` float32 ``[h, w]`` in 0..1: 0 where alpha is 0, a dome across every stroke
      (normalised by the local stroke width, so a thin stroke rises as high as a thick one) times
      satin ridges that repeat every ``stitch_px`` pixels along the stroke.
    * ``normal`` float32 ``[h, w, 3]`` unit vectors with z > 0, from the Sobel slope of ``height``
      scaled by ``NORMAL_STRENGTH``.
    * ``albedo`` float32 ``[h, w, 3]`` in 0..1, the logo colour (same BGR order as the input) with
      a seeded brightness change of up to +-6 % per ridge.

    ``angle_deg`` is the stitch direction in degrees (0 = along +x, 90 = along +y), so ridges
    repeat across it. With ``None`` each connected shape gets the direction in which its distance
    field rises (across its strokes), one angle per shape so the ridge phase stays continuous.
    """
    cv2, np = _deps()
    rgba = np.asarray(rgba)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("logo must be a uint8 RGBA (BGRA) image of shape [h, w, 4]")
    if stitch_px <= 0:
        raise ValueError("stitch_px must be positive")
    if int(rgba[..., 3].max()) == 0:
        raise ValueError("logo has no opaque pixels")
    h0, w0 = rgba.shape[:2]
    if w0 > MAX_LOGO_WIDTH:
        scale = MAX_LOGO_WIDTH / w0
        rgba = cv2.resize(rgba, (MAX_LOGO_WIDTH, max(1, round(h0 * scale))), interpolation=cv2.INTER_AREA)
    h, w = rgba.shape[:2]
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    mask = alpha > 0

    padded = np.pad(mask.astype(np.uint8), 1)
    dist = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1]
    half = np.maximum(_local_half_width(dist, cv2, np), 1e-6)
    t = np.clip(dist / half, 0.0, 1.0)
    dome = np.sqrt(t * (2.0 - t))

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    if angle_deg is None:
        count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
        theta = _stitch_angles(dist, mask, labels, count, np, cv2)[labels]
    else:
        theta = np.float32(math.radians(angle_deg))
    u = -xs * np.sin(theta) + ys * np.cos(theta)
    ridge = 0.5 + 0.5 * np.cos(2.0 * np.pi * u / stitch_px)
    height = (dome * ((1.0 - RIDGE_DEPTH) + RIDGE_DEPTH * ridge) * alpha).astype(np.float32)
    height[~mask] = 0.0

    sx = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    sy = cv2.Sobel(height, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    normal = np.dstack([-NORMAL_STRENGTH * sx, -NORMAL_STRENGTH * sy, np.ones_like(height)])
    normal = (normal / np.linalg.norm(normal, axis=2, keepdims=True)).astype(np.float32)

    jitter = np.random.default_rng(_JITTER_SEED).uniform(-1.0, 1.0, _JITTER_TABLE)
    index = np.floor(u / stitch_px).astype(np.int64) % _JITTER_TABLE
    gain = (1.0 + ALBEDO_JITTER * jitter[index]).astype(np.float32)
    albedo = np.clip(rgba[..., :3].astype(np.float32) / 255.0 * gain[..., None], 0.0, 1.0)
    return height, normal, albedo.astype(np.float32)
