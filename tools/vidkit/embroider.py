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
EDGE_AO_SIGMA = 2.0        # px, blur of the alpha edge

MIN_SHIRT_RATIO = 1.5      # shirt area at frame 0 must be at least this times the design's opaque area
GRID_COARSE = 7            # tracking grid over the design box
GRID_DENSE = 11            # used when the coarse grid keeps fewer than MIN_GRID_POINTS on the shirt
MIN_GRID_POINTS = 9


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
    rgba = cv2.resize(logo, (new_w, new_h), interpolation=interp)
    if rot:
        c, s_ = abs(math.cos(math.radians(rot))), abs(math.sin(math.radians(rot)))
        out_w, out_h = int(math.ceil(new_w * c + new_h * s_)), int(math.ceil(new_w * s_ + new_h * c))
        mat = cv2.getRotationMatrix2D((new_w / 2.0, new_h / 2.0), rot, 1.0)
        mat[0, 2] += out_w / 2.0 - new_w / 2.0
        mat[1, 2] += out_h / 2.0 - new_h / 2.0
        rgba = cv2.warpAffine(rgba, mat, (out_w, out_h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    x0 = int(round(at[0] - rgba.shape[1] / 2.0))
    y0 = int(round(at[1] - rgba.shape[0] / 2.0))
    return rgba, x0, y0


def _canvas_layer(rgba, x0, y0, size, np):
    """Thread maps of ``rgba`` placed on a frame-sized float32 layer: albedo 3, normal 3, height, alpha."""
    height, normal, albedo = thread_maps(rgba)
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    stack = np.concatenate([albedo, normal, height[..., None], alpha[..., None]], axis=2).astype(np.float32)
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
    from .screen import Refused, check_lost
    cv2, np = _deps()
    if logo is None or logo.ndim != 3 or logo.shape[2] != 4:
        raise ValueError("logo must be a 4-channel image with alpha (BGRA PNG)")
    frames = np.asarray(frames_bgr)
    n, height, fwidth = frames.shape[:3]
    size = (fwidth, height)
    rgba, x0, y0 = _place_logo(logo, width, rot, at, size, cv2, np)
    layer = _canvas_layer(rgba, x0, y0, size, np)
    opaque = layer[..., 7] > 0.5
    design_area = int(opaque.sum())
    if design_area == 0:
        raise ValueError("logo has no opaque pixels")
    ys, xs = np.nonzero(layer[..., 7] > 0)
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
    else:
        hand = np.zeros_like(shirt)

    src = _grid_points(box, shirt[0], np)
    if len(src) < MIN_VISIBLE_POINTS:
        raise Refused(f"track lost: {len(src)} tracking points on the shirt")
    queries = np.concatenate([np.zeros((len(src), 1)), src], axis=1)
    tracks, visible = pointtrack.track(rgb, queries)
    check_lost(visible, fps)

    out, lost, prev = [], 0, None
    hidden_share = (~visible).mean(axis=1)
    for t in range(n):
        try:
            warped = grid_warp(layer, src, tracks[t], visible[t], size)
            prev = warped
            if hidden_share[t] > 0.30:
                lost += 1
        except Refused:
            if prev is None:
                raise
            warped = prev
            lost += 1
        alpha = warped[..., 7] * shirt[t] * ~hand[t]
        normal = warped[..., 3:6]
        normal = normal / np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-6)
        out.append(shade(frames[t], warped[..., 0:3], normal, warped[..., 6], alpha))
    return np.stack(out), {"frames": n, "lost_frames": lost, "shirt_area_ratio": round(ratio, 3)}


def embroider(clip, logo, out, at, width, rot=0.0, hand_points=None, qa_dir=None):
    """Stitch ``logo`` (BGRA PNG path) onto the clothing at ``at`` in ``clip`` and write ``out``.

    The design is thread (``thread_maps``) warped by a mesh that follows 7x7 tracked points on the
    shirt (``grid_warp``), lit like the cloth around it (``shade``) and shown only where SAM 2.1
    says shirt and not hand. ``hand_points`` are ``[x, y]`` clicks on one occluding hand at frame
    0. The clip is decoded whole into memory; output is H.264 crf 15 with the audio copied.
    Returns ``{"frames", "lost_frames", "shirt_area_ratio"}``; raises ``screen.Refused`` when the
    track or the shirt cannot be trusted.
    """
    cv2, _ = _deps()
    from . import ff, screen
    logo_img = cv2.imread(str(logo), cv2.IMREAD_UNCHANGED)
    if logo_img is None:
        raise ValueError(f"logo is not a readable image: {logo}")
    if logo_img.ndim != 3 or logo_img.shape[2] != 4:
        raise ValueError(f"logo must be a 4-channel PNG with alpha: {logo}")
    info = ff.probe(str(clip))["video"]
    if not info:
        raise ValueError(f"clip has no video stream: {clip}")
    w, h, fps = info["width"], info["height"], info["fps"] or 30.0
    frames = screen._decode(str(clip), w, h)
    rendered, res = _render(frames, logo_img, at, width, rot, hand_points, fps)
    screen._encode(iter(rendered), clip, out, w, h, fps)
    if qa_dir:
        from . import sheet
        os.makedirs(qa_dir, exist_ok=True)
        sheet.contact_sheet(str(out), os.path.join(str(qa_dir), "qa-embroider.jpg"))
    return res
