"""Embroider a logo onto clothing: raised satin thread instead of flat ink.

Why this is not part of ``bond.py``: a print is flat ink, so ``bond`` multiplies the logo into the
cloth and the result has no relief of its own. Embroidery is thread stitched on top of the cloth.
It has its own height (a rounded ridge along each stroke, fine ridges from the stitches), its own
surface normal and its own shading, and it has to follow the cloth per point rather than through
one global warp. This module builds the thread surface; later phases add the warp and shading.

Needs ``cv2`` and ``numpy`` (shared venv); imported lazily so vidkit stays importable without them.
"""
import math
import os

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
EDGE_AO_SIGMA = 1.0        # px, blur of the alpha edge

MIN_STROKE_HALF_PX = 1.0   # thin strokes (25th percentile of the centre-line half-width, output px) are grown to this
SUPERSAMPLE = 3            # relief is computed at this multiple of the placed size, then area-averaged down
STITCH_OUT_PX = 3.0        # satin ridge spacing along a stroke, in output pixels
SATIN_SHEEN = 0.55         # directional sheen of the satin columns (peak, added to luminance)
RAISE_SHADOW_MAX = 0.28    # darkening of the cloth right next to the thread, on the side away from the light
RAISE_SHADOW_OFFSET_PX = 1.5   # shadow is displaced this far away from the light
RAISE_SHADOW_SIGMA = 1.1   # px, softness of the raised shadow
RAISE_SHADOW_REACH = 6     # px; the cloth farther than this from the design is never touched
GROW_SMOOTH_PX = 1.5       # px, how far the width measure is averaged along a stroke so its outline stays smooth
RELIEF_STRENGTH = 3.0      # NORMAL_STRENGTH of the supersampled relief, per output pixel
RELIEF_RIDGE_DEPTH = 0.45  # RIDGE_DEPTH of the supersampled relief: satin ridges stand out more than in thread_maps
RELIEF_MAX = 1.6          # clamp of the diffuse relief factor
EDGE_FUZZ = 0.25           # +- alpha jitter on the one-pixel boundary band, so the outline is not razor clean
_FUZZ_SEED = 241

MIN_SHIRT_RATIO = 1.5      # shirt area at frame 0 must be at least this times the design's opaque area
GRID_COARSE = 7            # tracking grid over the design box
GRID_DENSE = 11            # used when the coarse grid keeps fewer than MIN_GRID_POINTS on the shirt
MIN_GRID_POINTS = 9
SHIRT_KEEP_SHARE = 0.5     # a frame whose shirt under the design falls below this share of frame 0's is a bad frame


def _deps():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("embroider needs cv2 and numpy: run tools/setup.sh and use the venv python") from exc
    return cv2, np


def _local_half_width(dist, cv2, np):
    """Half-width of the stroke each pixel belongs to: the radius of the widest inscribed circle
    that covers it.

    Every pixel with distance value ``d`` stands for a circle of radius ``d``; that value is
    spread over the disc and the maximum is kept. Radii are bucketed (each bucket 15 % wider than
    the last, the disc takes the bucket's upper radius) so a big logo stays fast. Pixels outside
    the shape (distance 0) stay 0.
    """
    out = dist.copy()
    top = float(dist.max())
    low = 0.0
    high = 1.0
    while low < top:
        sel = (dist > low) & (dist <= high)
        if sel.any():
            radius = int(math.ceil(high))
            k = 2 * radius + 1
            grown = cv2.dilate(np.where(sel, dist, 0.0).astype(np.float32),
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            out = np.where(dist > 0, np.maximum(out, grown), out)
        low = high
        high = max(high + 1.0, high * 1.15)
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


def _thread_core(rgba, stitch_px, angle_deg, strength=None, ridge_depth=None):
    """The work of ``thread_maps``, plus the stitch angle per pixel: ``(height, normal, albedo, theta)``.

    ``theta`` (radians) is the direction the stitches run in: across the stroke. ``strength`` and
    ``ridge_depth`` default to ``NORMAL_STRENGTH`` and ``RIDGE_DEPTH``."""
    strength = NORMAL_STRENGTH if strength is None else strength
    ridge_depth = RIDGE_DEPTH if ridge_depth is None else ridge_depth
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
    height = (dome * ((1.0 - ridge_depth) + ridge_depth * ridge) * alpha).astype(np.float32)
    height[~mask] = 0.0

    sx = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    sy = cv2.Sobel(height, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    normal = np.dstack([-strength * sx, -strength * sy, np.ones_like(height)])
    normal = (normal / np.linalg.norm(normal, axis=2, keepdims=True)).astype(np.float32)

    jitter = np.random.default_rng(_JITTER_SEED).uniform(-1.0, 1.0, _JITTER_TABLE)
    index = np.floor(u / stitch_px).astype(np.int64) % _JITTER_TABLE
    gain = (1.0 + ALBEDO_JITTER * jitter[index]).astype(np.float32)
    albedo = np.clip(rgba[..., :3].astype(np.float32) / 255.0 * gain[..., None], 0.0, 1.0)
    return height, normal, albedo.astype(np.float32), np.broadcast_to(theta, height.shape).astype(np.float32)


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
    return _thread_core(rgba, stitch_px, angle_deg)[:3]


def _premultiplied(img, np):
    f = img.astype(np.float32)
    f[..., :3] *= f[..., 3:4] / 255.0
    return f


def _straight(img, np):
    a = img[..., 3:4]
    rgb = np.where(a > 1e-3, img[..., :3] * (255.0 / np.maximum(a, 1e-3)), 0.0)
    return np.clip(np.rint(np.concatenate([rgb, a], axis=2)), 0, 255).astype(np.uint8)


def _resize_rgba(img, size, interp, cv2, np):
    """Resize BGRA with premultiplied colour, so transparent pixels never bleed a dark fringe."""
    return _straight(cv2.resize(_premultiplied(img, np), size, interpolation=interp), np)


def _nearest_valid(valid, cv2, np):
    """Index arrays ``(ys, xs)`` giving, for every pixel, the nearest pixel where ``valid`` is True."""
    inv = (~valid).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    zy, zx = np.nonzero(valid)
    idx = labels - 1
    return zy[idx], zx[idx]


def _stroke_field(alpha, cv2, np):
    """Local stroke half-width of an alpha channel: ``(half, centre, scale)``.

    Computed at ``scale`` (1..4) times the size of ``alpha``. ``half`` is in output pixels (about
    0.5 for a one-pixel line, 1.6 for a stroke 3.2 px wide); ``centre`` marks the centre-line
    pixels of the strokes (where the distance to the outline is the local maximum), so a long
    thin line counts by its length and not by the area its edge pixels add.
    """
    h, w = alpha.shape
    s = int(max(1, min(4, math.sqrt(4e6 / float(h * w)))))
    big = cv2.resize(alpha, (w * s, h * s), interpolation=cv2.INTER_CUBIC) if s > 1 else alpha
    mask = big >= 128
    dist = cv2.distanceTransform(np.pad(mask.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    wide = _local_half_width(dist, cv2, np)
    centre = mask & (dist >= wide - 1e-3)
    return (wide - 0.5) / s, centre, s


def _fill_holes(logo, shrink, cv2, np):
    """Close holes in the alpha that are smaller than a third of an output pixel.

    ``shrink`` is source pixels per output pixel. A printed or grainy logo has speckled alpha;
    averaged down to thread size no pixel stays opaque and the design turns into faded ink.
    Thread is solid, so alpha holes up to ``0.6 * shrink`` source px wide are filled (colour from
    the nearest solid pixel). A logo that is not being shrunk is returned unchanged.
    """
    radius = int(round(0.3 * shrink))
    if radius < 1:
        return logo
    k = 2 * radius + 1
    alpha = logo[..., 3]
    closed = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    filled = closed > alpha
    solid = alpha >= 200
    out = logo.copy()
    if solid.any():
        ny, nx = _nearest_valid(solid, cv2, np)
        out[..., :3][filled] = logo[ny, nx, :3][filled]
    out[..., 3] = closed
    return out


def stroke_half_width(rgba):
    """25th percentile of the stroke half-width along the stroke centre-lines of ``rgba``.

    In the pixels of ``rgba``, measured on the alpha channel at up to 4x resolution so a sub-pixel
    change in width shows. A one-pixel line measures about 0.5; a stroke 3.2 px wide measures 1.6.
    """
    cv2, np = _deps()
    half, centre, _ = _stroke_field(np.asarray(rgba)[..., 3], cv2, np)
    if not centre.any():
        return 0.0
    return float(np.percentile(half[centre], 25))


def _grow(img, min_half, cv2, np):
    """Widen only the strokes thinner than ``min_half``, each up to that half-width.

    A pixel whose local half-width is ``hw`` pushes the outline out by ``min_half - hw``, so thin
    lines (an underline, an icon outline) reach the minimum while strokes that are already wide
    keep their shape and counters stay open. The push is sub-pixel (antialiased). New pixels take
    the colour of the nearest opaque pixel; the existing opaque pixels are kept.
    """
    alpha = img[..., 3].astype(np.float32) / 255.0
    solid = alpha >= 0.5
    half, mask_big, s = _stroke_field(img[..., 3], cv2, np)
    local = half[s // 2::s, s // 2::s][:alpha.shape[0], :alpha.shape[1]]
    need = np.where(solid, np.maximum(min_half - local, 0.0), 0.0).astype(np.float32)
    weight = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), GROW_SMOOTH_PX)
    need = np.where(solid, cv2.GaussianBlur(need, (0, 0), GROW_SMOOTH_PX) / np.maximum(weight, 1e-3), 0.0)
    cover = np.zeros_like(alpha)
    levels = np.unique(np.round(need[need > 0] * 4.0) / 4.0)
    for radius in levels:
        src = solid & (np.abs(need - radius) <= 0.125 + 1e-6)
        if not src.any():
            continue
        dist = cv2.distanceTransform((~src).astype(np.uint8), cv2.DIST_L2, 5)
        cover = np.maximum(cover, np.clip(radius + 1.0 - dist, 0.0, 1.0))
    cover[solid] = 0.0
    new_alpha = np.maximum(alpha, cover)
    changed = new_alpha > alpha
    ny, nx = _nearest_valid(solid, cv2, np)
    out = img.copy()
    out[..., :3][changed] = img[ny, nx, :3][changed]
    out[..., 3] = np.rint(new_alpha * 255.0).astype(np.uint8)
    return out


def ensure_min_stroke(rgba, min_half=None):
    """Return ``rgba`` with thin strokes widened until ``stroke_half_width`` reaches ``min_half``.

    ``min_half`` defaults to ``MIN_STROKE_HALF_PX``. Thread thinner than about three output pixels
    cannot show a satin ridge at all, so thin strokes are grown (colour extended from the nearest
    opaque pixel) before stitching; wide strokes are left as they are. A logo already wide enough
    is returned unchanged.
    """
    cv2, np = _deps()
    target = MIN_STROKE_HALF_PX if min_half is None else float(min_half)
    base = np.asarray(rgba)
    if stroke_half_width(base) >= target:
        return base
    out = base
    for extra in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        out = _grow(base, target + extra, cv2, np)
        if stroke_half_width(out) >= target:
            break
    return out


def edge_fuzz(alpha):
    """Jitter the alpha of the one-pixel boundary band by up to ``EDGE_FUZZ``; deterministic.

    Real thread has a slightly ragged outline. Pixels inside the shape (all eight neighbours
    covered) and pixels outside it are returned unchanged.
    """
    cv2, np = _deps()
    alpha = np.asarray(alpha, np.float32)
    covered = alpha > 0
    inner = cv2.erode(covered.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    band = covered & ~inner
    noise = np.random.default_rng(_FUZZ_SEED).uniform(-1.0, 1.0, alpha.shape).astype(np.float32)
    out = alpha.copy()
    out[band] = np.clip(alpha[band] + EDGE_FUZZ * noise[band], 0.0, 1.0)
    return out


def _light_dir(np):
    ldir = np.array(LIGHT_DIR, np.float32)
    return ldir / np.linalg.norm(ldir)


def relief_maps(rgba, stitch_px=None, angle_deg=None):
    """Light-independent thread look at output size: ``(albedo, alpha, relief, sheen)``.

    The thread surface is built at ``SUPERSAMPLE`` times the size of ``rgba`` (so a ridge only
    two or three output pixels apart is still resolved) and area-averaged back down.
    ``relief`` ``[h, w]`` is the diffuse factor (1.0 on flat thread under the fixed light, above
    1 on ridges facing it, below 1 in valleys and at the boundary); ``sheen`` ``[h, w]`` is the
    directional satin highlight, strongest where the stitches run across the light and on the
    crest of a column. ``albedo`` is the logo colour with the per-ridge jitter. Values outside
    the shape repeat the nearest thread pixel so a warp never blends them with black.
    ``stitch_px`` (output pixels) defaults to ``STITCH_OUT_PX``.
    """
    cv2, np = _deps()
    stitch_px = STITCH_OUT_PX if stitch_px is None else stitch_px
    rgba = np.asarray(rgba)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("logo must be a uint8 RGBA (BGRA) image of shape [h, w, 4]")
    h, w = rgba.shape[:2]
    s = max(1, min(SUPERSAMPLE, MAX_LOGO_WIDTH // w))
    big = _resize_rgba(rgba, (w * s, h * s), cv2.INTER_CUBIC, cv2, np) if s > 1 else rgba.copy()
    big[..., 3] = np.where(big[..., 3] >= 128, 255, 0)
    height, normal, albedo, theta = _thread_core(big, stitch_px * s, angle_deg, RELIEF_STRENGTH * s, RELIEF_RIDGE_DEPTH)

    ldir = _light_dir(np)
    lam = np.clip(normal @ ldir, 0.0, 1.0)
    flat = AMBIENT + (1.0 - AMBIENT) * float(ldir[2])
    cavity = 1.0 - CAVITY_MAX * (1.0 - height)
    cover = (big[..., 3] > 0).astype(np.float32)
    edge = 1.0 - EDGE_AO_MAX * (1.0 - cv2.GaussianBlur(cover, (0, 0), EDGE_AO_SIGMA * s))
    relief = np.clip((AMBIENT + (1.0 - AMBIENT) * lam) / flat * cavity * edge, 0.0, RELIEF_MAX)

    light_xy = ldir[:2] / np.linalg.norm(ldir[:2])
    across = np.cos(theta) * light_xy[0] + np.sin(theta) * light_xy[1]
    aniso = np.sqrt(np.clip(1.0 - across * across, 0.0, 1.0))
    sheen = (SPECULAR_MAX * lam ** SPECULAR_POWER + SATIN_SHEEN * aniso * height ** 3) * cover

    weight = cv2.resize(cover, (w, h), interpolation=cv2.INTER_AREA)
    stack = np.dstack([albedo, relief, sheen]) * cover[..., None]
    small = cv2.resize(stack, (w, h), interpolation=cv2.INTER_AREA) if s > 1 else stack
    valid = weight > 0.05
    small = small / np.maximum(weight, 1e-6)[..., None]
    if valid.any() and not valid.all():
        ny, nx = _nearest_valid(valid, cv2, np)
        small = small[ny, nx]
    small = small.astype(np.float32)
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    return small[..., 0:3], alpha, small[..., 3], small[..., 4]


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


def shade(frame_bgr, albedo, normal, height, alpha, relief=None, sheen=None, under=None):
    """Composite warped thread onto the frame, lit like the cloth around it.

    ``frame_bgr`` is uint8 ``[H, W, 3]``; ``albedo`` ``[H, W, 3]`` 0..1 BGR and ``alpha``
    ``[H, W]`` 0..1 are already warped to the frame. The local cloth light is the frame luminance
    blurred by ``CLOTH_LIGHT_SIGMA``, divided by its median under the thread (clamped to
    ``LIGHT_GAIN_RANGE``), so thread tracks every fold and shadow of the cloth while its mean
    brightness stays the albedo.

    Colour is kept: the light only scales the luminance (Y of YCrCb); the chroma stays the thread's
    own, so a teal thread stays teal. Luminance is ``albedo_Y * relief * gain`` plus
    ``sheen * (0.35 + 0.65 * albedo_Y) * gain`` (dark thread gets a dimmer highlight).

    ``relief`` and ``sheen`` ``[H, W]`` come from ``relief_maps`` (already warped). When they are
    None they are derived from ``normal`` ``[H, W, 3]`` and ``height`` ``[H, W]``: Lambert with
    ``LIGHT_DIR``, cavity darkening by ``CAVITY_MAX``, boundary darkening by ``EDGE_AO_MAX`` and a
    specular of ``SPECULAR_MAX * lambert**SPECULAR_POWER * height``. The thread is drawn over
    ``under`` (default the frame itself, which also feeds the light estimate); pixels with alpha 0
    return ``under`` unchanged. Returns uint8 BGR.
    """
    cv2, np = _deps()
    frame = np.asarray(frame_bgr)
    base = frame if under is None else np.asarray(under)
    alpha = np.clip(np.asarray(alpha, np.float32), 0.0, 1.0)
    albedo = np.ascontiguousarray(albedo, np.float32)

    lum = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    light = cv2.GaussianBlur(lum, (0, 0), CLOTH_LIGHT_SIGMA) / 255.0
    covered = alpha > 0.5
    ref = float(np.median(light[covered])) if covered.any() else float(light.mean())
    gain = np.clip(light / max(ref, 1e-3), *LIGHT_GAIN_RANGE)

    if relief is None:
        height = np.clip(np.asarray(height, np.float32), 0.0, 1.0)
        lambert = np.clip(np.asarray(normal, np.float32) @ _light_dir(np), 0.0, 1.0)
        cavity = 1.0 - CAVITY_MAX * (1.0 - height)
        edge = 1.0 - EDGE_AO_MAX * (1.0 - cv2.GaussianBlur(alpha, (0, 0), EDGE_AO_SIGMA))
        relief = (AMBIENT + (1.0 - AMBIENT) * lambert) * cavity * edge
        sheen = SPECULAR_MAX * lambert ** SPECULAR_POWER * height
    relief = np.asarray(relief, np.float32)
    sheen = np.asarray(sheen, np.float32)

    ycc = cv2.cvtColor(albedo, cv2.COLOR_BGR2YCrCb)
    y = ycc[..., 0]
    ycc[..., 0] = np.clip((y * relief + sheen * (0.35 + 0.65 * y)) * gain, 0.0, 1.0)
    thread = np.clip(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR), 0.0, 1.0) * 255.0

    out = base.astype(np.float32) * (1.0 - alpha[..., None]) + thread * alpha[..., None]
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    out[alpha <= 0] = base[alpha <= 0]
    return out


def raised_shadow(frame_bgr, alpha, valid):
    """Darken the cloth beside the thread, on the side away from the light: the thread stands up.

    ``alpha`` ``[H, W]`` 0..1 is the warped design; ``valid`` bool ``[H, W]`` marks the pixels that
    may change (shirt and not hand). The blurred alpha, displaced ``RAISE_SHADOW_OFFSET_PX`` away
    from the light, darkens the frame by up to ``RAISE_SHADOW_MAX``. Only pixels outside the
    design, inside ``valid`` and within ``RAISE_SHADOW_REACH`` px of the design change; every other
    pixel is returned exactly.
    """
    cv2, np = _deps()
    frame = np.asarray(frame_bgr)
    alpha = np.clip(np.asarray(alpha, np.float32), 0.0, 1.0)
    height, width = alpha.shape
    light_xy = _light_dir(np)[:2]
    shift = -light_xy / np.linalg.norm(light_xy) * RAISE_SHADOW_OFFSET_PX
    blurred = cv2.GaussianBlur(alpha, (0, 0), RAISE_SHADOW_SIGMA)
    moved = cv2.warpAffine(blurred, np.array([[1, 0, shift[0]], [0, 1, shift[1]]], np.float32), (width, height),
                           flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    k = 2 * RAISE_SHADOW_REACH + 1
    reach = cv2.dilate((alpha > 0).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0
    amount = RAISE_SHADOW_MAX * np.clip(moved, 0.0, 1.0) * (1.0 - alpha)
    amount[~(reach & np.asarray(valid, bool))] = 0.0
    out = np.clip(np.rint(frame.astype(np.float32) * (1.0 - amount[..., None])), 0, 255).astype(np.uint8)
    keep = amount <= 0
    out[keep] = frame[keep]
    return out


def _shade_layer(frame_bgr, layer, alpha, under=None):
    """``shade`` for a warped design layer (albedo 0:3, alpha 3, relief 4, sheen 5)."""
    return shade(frame_bgr, layer[..., 0:3], None, None, alpha, relief=layer[..., 4], sheen=layer[..., 5],
                 under=under)


def _place_logo(logo, width, rot, at, size, cv2, np):
    """Scale ``logo`` (BGRA) to ``width`` px, rotate by ``rot`` deg, centre it at ``at`` on a canvas.

    Returns ``(rgba, x0, y0)``: the scaled and rotated logo and its top-left corner on the canvas
    (may be negative when the logo hangs over the frame edge).
    """
    if width <= 0 or width > MAX_LOGO_WIDTH:
        raise ValueError(f"--width must be 1..{MAX_LOGO_WIDTH}, got {width}")
    h0, w0 = logo.shape[:2]
    scale = width / float(w0)
    new_w, new_h = max(int(round(w0 * scale)), 1), max(int(round(h0 * scale)), 1)
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    rgba = _resize_rgba(_fill_holes(logo, 1.0 / scale, cv2, np), (new_w, new_h), interp, cv2, np)
    if rot:
        c, s_ = abs(math.cos(math.radians(rot))), abs(math.sin(math.radians(rot)))
        out_w, out_h = int(math.ceil(new_w * c + new_h * s_)), int(math.ceil(new_w * s_ + new_h * c))
        mat = cv2.getRotationMatrix2D((new_w / 2.0, new_h / 2.0), rot, 1.0)
        mat[0, 2] += out_w / 2.0 - new_w / 2.0
        mat[1, 2] += out_h / 2.0 - new_h / 2.0
        rgba = _straight(cv2.warpAffine(_premultiplied(rgba, np), mat, (out_w, out_h), flags=cv2.INTER_LINEAR,
                                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)), np)
    x0 = int(round(at[0] - rgba.shape[1] / 2.0))
    y0 = int(round(at[1] - rgba.shape[0] / 2.0))
    return rgba, x0, y0


def _canvas_layer(rgba, x0, y0, size, np):
    """Thread look of ``rgba`` placed on a frame-sized float32 layer: albedo 3, alpha, relief, sheen."""
    albedo, alpha, relief, sheen = relief_maps(ensure_min_stroke(rgba))
    alpha = edge_fuzz(alpha)
    stack = np.concatenate([albedo, alpha[..., None], relief[..., None], sheen[..., None]], axis=2).astype(np.float32)
    width, frame_h = size
    layer = np.zeros((frame_h, width, stack.shape[2]), np.float32)
    h, w = stack.shape[:2]
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + w, width), min(y0 + h, frame_h)
    if cx1 <= cx0 or cy1 <= cy0:
        raise ValueError("the design is entirely outside the frame")
    layer[cy0:cy1, cx0:cx1] = stack[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    return layer


def _grid_points(box, shirt0, np):
    """Tracking points over the design box ``(x0, y0, x1, y1)``, kept where frame 0 shows shirt."""
    x0, y0, x1, y1 = box
    height, width = shirt0.shape
    pts = np.zeros((0, 2), np.float64)
    for n in (GRID_COARSE, GRID_DENSE):
        gx, gy = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
        cand = np.stack([gx.ravel(), gy.ravel()], axis=1)
        ix = np.clip(np.rint(cand[:, 0]).astype(int), 0, width - 1)
        iy = np.clip(np.rint(cand[:, 1]).astype(int), 0, height - 1)
        pts = cand[shirt0[iy, ix]]
        if len(pts) >= MIN_GRID_POINTS:
            break
    return pts


def _render(frames_bgr, logo, at, width, rot, hand_points, fps):
    """Composite the embroidered design onto every frame; no file I/O.

    ``frames_bgr`` uint8 ``[T, H, W, 3]``, ``logo`` BGRA uint8, ``at`` (x, y) design centre at
    frame 0, ``width`` px, ``rot`` deg, ``hand_points`` list of ``[x, y]`` on frame 0 that all
    belong to the occluding hand region (SAM prompts them together as one object, label 1) or
    None. Returns ``(frames uint8 [T, H, W, 3], info)``; ``embroider`` encodes the frames.
    """
    from . import pointtrack, segment
    from .screen import LOST_POINT_SHARE, OCCLUDER_MAX_SHARE, Refused, bad_runs, check_lost
    cv2, np = _deps()
    if logo is None or logo.ndim != 3 or logo.shape[2] != 4:
        raise ValueError("logo must be a 4-channel image with alpha (BGRA PNG)")
    frames = np.asarray(frames_bgr)
    n, height, fwidth = frames.shape[:3]
    size = (fwidth, height)
    rgba, x0, y0 = _place_logo(logo, width, rot, at, size, cv2, np)
    layer = _canvas_layer(rgba, x0, y0, size, np)
    opaque = layer[..., 3] > 0.5
    design_area = int(opaque.sum())
    if design_area == 0:
        raise ValueError("logo has no opaque pixels")
    ys, xs = np.nonzero(layer[..., 3] > 0)
    box = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))

    rgb = np.ascontiguousarray(frames[..., ::-1])
    shirt = segment.masks(rgb, 0, points=[[float(at[0]), float(at[1])]])
    ax, ay = int(round(min(max(at[0], 0), fwidth - 1))), int(round(min(max(at[1], 0), height - 1)))
    if not shirt[0][ay, ax]:
        raise Refused("--at is not on the shirt")
    ratio = float(shirt[0].sum()) / design_area
    if ratio < MIN_SHIRT_RATIO:
        raise Refused(f"shirt area too small for design ({ratio:.2f})")
    if hand_points:
        hand = segment.masks(rgb, 0, points=[[float(x), float(y)] for x, y in hand_points])
        if not hand[0].any():
            raise Refused("hand mask is empty at frame 0")
        covered = float((hand[0] & opaque).sum()) / design_area
        if covered > OCCLUDER_MAX_SHARE:
            raise Refused(f"hand mask covers {round(100 * covered)}% of the design (click landed on the shirt?)")
    else:
        hand = np.zeros_like(shirt)

    src = _grid_points(box, shirt[0], np)
    if len(src) < MIN_GRID_POINTS:
        raise Refused(f"track lost: only {len(src)} grid points on the shirt")
    queries = np.concatenate([np.zeros((len(src), 1)), src], axis=1)
    tracks, visible = pointtrack.track(rgb, queries)
    check_lost(visible, fps)

    out, prev = [], None
    hidden = (~visible).mean(axis=1) > LOST_POINT_SHARE
    fallback = np.zeros(n, bool)
    shirt_bad = np.zeros(n, bool)
    share0 = 0.0
    for t in range(n):
        try:
            warped = grid_warp(layer, src, tracks[t], visible[t], size)
            prev = warped
        except Refused:
            if prev is None:
                raise
            warped = prev
            fallback[t] = True
        valid = shirt[t] & ~hand[t]
        design = warped[..., 3]
        footprint = design > 0.5
        if footprint.any():
            share = float((footprint & (shirt[t] | hand[t])).sum()) / float(footprint.sum())
            if t == 0:
                share0 = share
            elif share < SHIRT_KEEP_SHARE * share0:
                shirt_bad[t] = True
        out.append(_shade_layer(frames[t], warped, design * valid, raised_shadow(frames[t], design, valid)))
    for flags, text in ((fallback, "track lost on frames {a}-{b} (mesh warp failed)"),
                        (shirt_bad, "shirt lost on frames {a}-{b}")):
        runs = bad_runs(flags, fps)
        if runs:
            raise Refused(text.format(a=runs[0][0], b=runs[0][1]))
    lost = int((hidden | fallback | shirt_bad).sum())
    return np.stack(out), {"frames": n, "lost_frames": lost, "shirt_area_ratio": round(ratio, 3)}


def _read_logo(path):
    """The logo as a BGRA uint8 array; 16-bit is scaled down, other dtypes and non-alpha files refused."""
    cv2, _ = _deps()
    from . import screen
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"logo is not a readable image: {path}")
    if img.ndim != 3 or img.shape[2] != 4:
        raise ValueError(f"logo must be a 4-channel PNG with alpha: {path}")
    return screen.to_uint8(img, f"logo {path}")


def embroider(clip, logo, out, at, width, rot=0.0, hand_points=None, qa_dir=None):
    """Stitch ``logo`` (BGRA PNG path) onto the clothing at ``at`` in ``clip`` and write ``out``.

    Thin strokes are widened (``ensure_min_stroke``), the thread look is built at 3x size and
    averaged down (``relief_maps``), warped by a mesh that follows 7x7 tracked points on the shirt
    (``grid_warp``), lit like the cloth around it with its own colour kept (``shade``), given a
    soft raised shadow on the cloth (``raised_shadow``) and shown only where SAM 2.1 says shirt
    and not hand. ``hand_points`` are ``[x, y]`` clicks on one occluding hand at frame
    0. The clip is decoded whole into memory; output is H.264 crf 15 with the audio re-encoded to AAC
    and padded to the video length.
    Returns ``{"frames", "lost_frames", "shirt_area_ratio"}``; raises ``screen.Refused`` when the
    track or the shirt cannot be trusted: the hand mask empty or covering over 60% of the design
    at frame 0, fewer than ``MIN_GRID_POINTS`` tracking points, the mesh warp failing, or the
    shirt under the design shrinking below half its frame-0 share, the last two for 0.5 s running.
    """
    cv2, _ = _deps()
    from . import ff, screen
    logo_img = _read_logo(logo)
    info = ff.probe(str(clip))["video"]
    if not info:
        raise ValueError(f"clip has no video stream: {clip}")
    w, h, fps = info["width"], info["height"], screen._fps_of(info, clip)
    frames = screen._decode(str(clip), w, h)
    rendered, res = _render(frames, logo_img, at, width, rot, hand_points, fps)
    screen._encode(iter(rendered), clip, out, w, h, fps)
    if qa_dir:
        from . import sheet
        os.makedirs(qa_dir, exist_ok=True)
        sheet.contact_sheet(str(out), os.path.join(str(qa_dir), "qa-embroider.jpg"))
    return res
