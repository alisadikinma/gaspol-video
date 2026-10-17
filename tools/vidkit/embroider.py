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

MIN_VISIBLE_POINTS = 4     # fewer visible mesh points than this and the track counts as lost
MIN_HULL_AREA = 1.0        # px^2; a visible set spanning less is collinear and refused
LIGHT_DIR = (-0.35, -0.35, 0.87)   # direction TOWARD the light, image axes (x right, y down): upper left
CLOTH_LIGHT_SIGMA = 12.0   # px, blur of the frame luminance that gives the local cloth light
LIGHT_GAIN_RANGE = (0.4, 1.6)      # clamp of (local light / median light under the thread)
AMBIENT = 0.35             # thread = albedo * (AMBIENT + (1 - AMBIENT) * lambert) * light
SPECULAR_MAX = 0.12        # peak specular added on ridges
SPECULAR_POWER = 16        # lambert ** SPECULAR_POWER, weighted by height
CAVITY_MAX = 0.15          # darkening in valleys: 1 - CAVITY_MAX * (1 - height)
EDGE_AO_MAX = 0.30         # darkening at the thread boundary, fading over EDGE_AO_SIGMA
EDGE_AO_SIGMA = 2.0        # px, blur of the alpha edge


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


def _triangles(src, np, cv2):
    """Delaunay triangles of ``src`` as index triples (Subdiv2D, no scipy)."""
    lo = src.min(axis=0) - 10.0
    hi = src.max(axis=0) + 10.0
    sub = cv2.Subdiv2D((int(lo[0]), int(lo[1]), int(hi[0] - lo[0]) + 2, int(hi[1] - lo[1]) + 2))
    index = {}
    for i, (x, y) in enumerate(src):
        key = (round(float(x), 3), round(float(y), 3))
        if key in index:
            continue
        index[key] = i
        sub.insert((float(x), float(y)))
    tris = []
    for t in sub.getTriangleList():
        keys = [(round(float(t[k]), 3), round(float(t[k + 1]), 3)) for k in (0, 2, 4)]
        if all(k in index for k in keys):
            tris.append([index[k] for k in keys])
    return np.array(tris, np.int64)


def grid_warp(layer, src_pts, dst_pts, visible, size):
    """Warp ``layer`` from the mesh ``src_pts`` (frame 0) to ``dst_pts`` (frame t).

    ``layer`` is a float32 or uint8 ``[H, W, C]`` canvas already placed in frame-0 coordinates at
    full frame size ``size = (W, H)``. ``C`` is free: 4 for RGBA, or the height, normal, albedo and
    alpha maps stacked into one multi-channel layer so that all of them warp identically.
    ``src_pts`` and ``dst_pts`` are ``[N, 2]`` (x, y); they need not form a regular grid.
    ``visible`` is a bool ``[N]``; only visible points are used.

    The warp is piecewise affine over a Delaunay triangulation of the visible source points. A
    dense backward map is built (each destination pixel inside a destination triangle gets its
    source position from barycentric coordinates) and applied with ``cv2.remap`` (bilinear). Pixels
    outside the destination hull get 0 in every channel, alpha included. Returns an array of the
    same shape and dtype as ``layer``. Raises ``Refused("track lost: <n> visible points")`` with
    fewer than ``MIN_VISIBLE_POINTS`` visible points or when they span under ``MIN_HULL_AREA`` px^2.
    """
    from tools.vidkit.screen import Refused
    cv2, np = _deps()
    layer = np.asarray(layer)
    width, height = int(size[0]), int(size[1])
    if layer.ndim != 3 or layer.shape[:2] != (height, width):
        raise ValueError("layer must be [H, W, C] matching size=(W, H)")
    src = np.asarray(src_pts, np.float64).reshape(-1, 2)
    dst = np.asarray(dst_pts, np.float64).reshape(-1, 2)
    vis = np.asarray(visible, bool).reshape(-1)
    if not (len(src) == len(dst) == len(vis)):
        raise ValueError("src_pts, dst_pts and visible must have the same length")
    n = int(vis.sum())
    src, dst = src[vis], dst[vis]
    if n < MIN_VISIBLE_POINTS or cv2.contourArea(cv2.convexHull(src.astype(np.float32))) < MIN_HULL_AREA \
            or cv2.contourArea(cv2.convexHull(dst.astype(np.float32))) < MIN_HULL_AREA:
        raise Refused("track lost: %d visible points" % n)

    map_x = np.full((height, width), -1.0, np.float32)
    map_y = np.full((height, width), -1.0, np.float32)
    eps = 1e-6
    for a, b, c in _triangles(src, np, cv2):
        d0, d1, d2 = dst[a], dst[b], dst[c]
        det = (d1[0] - d0[0]) * (d2[1] - d0[1]) - (d2[0] - d0[0]) * (d1[1] - d0[1])
        if abs(det) < 1e-9:
            continue
        x0 = max(int(math.floor(min(d0[0], d1[0], d2[0]))), 0)
        x1 = min(int(math.ceil(max(d0[0], d1[0], d2[0]))), width - 1)
        y0 = max(int(math.floor(min(d0[1], d1[1], d2[1]))), 0)
        y1 = min(int(math.ceil(max(d0[1], d1[1], d2[1]))), height - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        px, py = xs - d0[0], ys - d0[1]
        l1 = (px * (d2[1] - d0[1]) - (d2[0] - d0[0]) * py) / det
        l2 = ((d1[0] - d0[0]) * py - px * (d1[1] - d0[1])) / det
        l0 = 1.0 - l1 - l2
        inside = (l0 >= -eps) & (l1 >= -eps) & (l2 >= -eps)
        s0, s1, s2 = src[a], src[b], src[c]
        map_x[y0:y1 + 1, x0:x1 + 1][inside] = (l0 * s0[0] + l1 * s1[0] + l2 * s2[0])[inside]
        map_y[y0:y1 + 1, x0:x1 + 1][inside] = (l0 * s0[1] + l1 * s1[1] + l2 * s2[1])[inside]

    out = np.empty_like(layer)
    for c0 in range(0, layer.shape[2], 4):
        chunk = np.ascontiguousarray(layer[..., c0:c0 + 4])
        warped = cv2.remap(chunk, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        out[..., c0:c0 + 4] = warped.reshape(chunk.shape)
    return out


def shade(frame_bgr, albedo, normal, height, alpha):
    """Composite warped thread onto ``frame_bgr`` (uint8 ``[H, W, 3]``) lit like the cloth around it.

    ``albedo`` ``[H, W, 3]`` 0..1 BGR, ``normal`` ``[H, W, 3]``, ``height`` ``[H, W]`` 0..1 and
    ``alpha`` ``[H, W]`` 0..1 are already warped to the frame. The local cloth light is the frame
    luminance blurred by ``CLOTH_LIGHT_SIGMA``, divided by its median under the thread (clamped to
    ``LIGHT_GAIN_RANGE``), so thread tracks every fold and shadow of the cloth while its mean
    brightness stays the albedo. Lambert uses the fixed light ``LIGHT_DIR`` (upper left). A small
    specular (``SPECULAR_MAX * lambert**SPECULAR_POWER * height``) sits on ridges; valleys are
    darkened by ``CAVITY_MAX`` and the thread boundary by up to ``EDGE_AO_MAX``. Pixels with
    alpha 0 are returned unchanged. Returns uint8 BGR.
    """
    cv2, np = _deps()
    frame = np.asarray(frame_bgr)
    alpha = np.clip(np.asarray(alpha, np.float32), 0.0, 1.0)
    height = np.clip(np.asarray(height, np.float32), 0.0, 1.0)
    normal = np.asarray(normal, np.float32)
    albedo = np.asarray(albedo, np.float32)

    lum = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    light = cv2.GaussianBlur(lum, (0, 0), CLOTH_LIGHT_SIGMA) / 255.0
    covered = alpha > 0.5
    ref = float(np.median(light[covered])) if covered.any() else float(light.mean())
    gain = np.clip(light / max(ref, 1e-3), *LIGHT_GAIN_RANGE)

    ldir = np.array(LIGHT_DIR, np.float32)
    ldir /= np.linalg.norm(ldir)
    lambert = np.clip(normal @ ldir, 0.0, 1.0)
    diffuse = albedo * (AMBIENT + (1.0 - AMBIENT) * lambert)[..., None] * gain[..., None]
    specular = SPECULAR_MAX * lambert ** SPECULAR_POWER * height
    cavity = 1.0 - CAVITY_MAX * (1.0 - height)
    edge = 1.0 - EDGE_AO_MAX * (1.0 - cv2.GaussianBlur(alpha, (0, 0), EDGE_AO_SIGMA))
    thread = np.clip((diffuse + specular[..., None]) * (cavity * edge)[..., None], 0.0, 1.0) * 255.0

    out = frame.astype(np.float32) * (1.0 - alpha[..., None]) + thread * alpha[..., None]
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    out[alpha <= 0] = frame[alpha <= 0]
    return out
