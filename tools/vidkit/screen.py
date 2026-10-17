"""Screen corners for the screen-insert workflow.

A green-screen clip gives exact corners: key the green, take the largest blob, fit one line per
side and intersect them. A finger or hand over one edge only adds outlier points to that side's
line fit (RANSAC drops them), so the corner does not move. Contrast with ``tools/track_screen.py``,
which flood-fills from a seed and so follows whatever occludes the edge.

``corners_track`` follows a screen that has no key colour: it tracks points on and around the quad
with TAPNext++ and fits a homography per frame. ``check_track`` turns a bad track into ``Refused``.

Also holds ``OneEuro``, the One-Euro low-pass filter (Casiez et al. 2012) used to smooth corner
tracks. ``cv2`` and ``numpy`` are imported lazily so importing this module works on a bare python3.
"""
import math
import os
import subprocess
import tempfile

MIN_SCREEN_WIDTH_PX = 40
RANSAC_TOL_PX = 1.5
RANSAC_ITERS = 200
CORNER_MARGIN_PX = 6.0
MIN_QUAD_AREA_PX2 = 100.0
RING_OFFSET = 0.09        # ring distance outside the quad, as a fraction of sqrt(quad area)
GRID_N = 5                # inside grid is GRID_N x GRID_N, inset from the edges
GRID_INSET = 0.15
HOMOGRAPHY_TOL_PX = 3.0
LOST_POINT_SHARE = 0.30   # more than this share of points hidden counts as lost
LOST_SECONDS = 0.5
JUMP_DIAG_SHARE = 0.08
MIN_INLIER_RATIO = 0.5
ASPECT_TOL = 0.02         # panel aspect within 2% of the quad's is stretched, otherwise letterboxed
FEATHER_SIGMA = 0.75      # gaussian sigma of the quad mask edge: about 1.5 px wide transition
GAIN_RANGE = (0.6, 1.4)   # clamp of the luminance gain that matches the panel to the screen
GREEN_MISSING_MAX = 0.05
OCCLUDER_ERODE_PX = 4     # key-inverse is read this far inside the quad so the screen's own edge is not an occluder
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")


class Refused(RuntimeError):
    """The track cannot be trusted; the CLI prints ``refused: <message>`` and exits 2."""


def _deps():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("screen needs cv2 and numpy: run tools/setup.sh and use the venv python") from exc
    return cv2, np


class OneEuro:
    """One-Euro filter applied element-wise; state is kept per element."""

    def __init__(self, fps, min_cutoff=1.0, beta=0.05, d_cutoff=1.0):
        if not fps or fps <= 0:
            raise ValueError("fps must be > 0")
        self.fps = float(fps)
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x = None
        self._dx = None

    def _alpha(self, cutoff):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau * self.fps)

    def __call__(self, x):
        _, np = _deps()
        x = np.asarray(x, dtype=np.float64)
        if self._x is None:
            self._x = x.copy()
            self._dx = np.zeros_like(x)
            return x.copy()
        dx = (x - self._x) * self.fps
        a_d = self._alpha(self.d_cutoff)
        self._dx = a_d * dx + (1.0 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        tau = 1.0 / (2.0 * math.pi * cutoff)
        a = 1.0 / (1.0 + tau * self.fps)
        self._x = a * x + (1.0 - a) * self._x
        return self._x.copy()


def _ransac_line(pts, rng, np):
    """Return (point, unit direction) of the line with the most inliers, refit on them."""
    n = len(pts)
    best = None
    for _ in range(RANSAC_ITERS):
        i, j = rng.choice(n, 2, replace=False)
        d = pts[j] - pts[i]
        norm = np.hypot(*d)
        if norm < 1e-6:
            continue
        d = d / norm
        dist = np.abs((pts[:, 0] - pts[i, 0]) * d[1] - (pts[:, 1] - pts[i, 1]) * d[0])
        inl = dist <= RANSAC_TOL_PX
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < 2:
        return None
    sel = pts[best]
    c = sel.mean(axis=0)
    _, _, vt = np.linalg.svd(sel - c)
    return c, vt[0]


def _intersect(l1, l2, np):
    (p, d), (q, e) = l1, l2
    a = np.array([[d[0], -e[0]], [d[1], -e[1]]])
    if abs(np.linalg.det(a)) < 1e-9:
        return None
    t = np.linalg.solve(a, q - p)[0]
    return p + t * d


def _initial_quad(contour, cv2, np):
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for eps in (0.02, 0.03, 0.05, 0.08):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float64)
    return cv2.boxPoints(cv2.minAreaRect(hull)).astype(np.float64)


def _clockwise_from_top_left(quad, np):
    c = quad.mean(axis=0)
    ang = np.arctan2(quad[:, 1] - c[1], quad[:, 0] - c[0])
    quad = quad[np.argsort(ang)]  # image coords (y down): increasing angle is clockwise on screen
    start = int(np.argmin(quad.sum(axis=1)))
    return np.roll(quad, -start, axis=0)


def corners_green(frame_bgr, hue=(40, 85), sat_min=80, val_min=60):
    """Four corners of the green screen, clockwise from top-left, float32 [4, 2]; None if no key.

    Each side is a RANSAC line over its edge points, so an occluding finger does not move a
    corner. Corners may lie outside the frame when the screen is cut by the border.
    """
    cv2, np = _deps()
    h, w = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (hue[0], sat_min, val_min), (hue[1], 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (labels == big).astype(np.uint8) * 255
    contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
    if min(rw, rh) < MIN_SCREEN_WIDTH_PX:
        return None

    quad = _clockwise_from_top_left(_initial_quad(contour, cv2, np), np)
    pts = contour.reshape(-1, 2).astype(np.float64)
    on_border = (pts[:, 0] <= 0) | (pts[:, 1] <= 0) | (pts[:, 0] >= w - 1) | (pts[:, 1] >= h - 1)
    pts = pts[~on_border]
    if len(pts) < 8:
        return None

    def seg_dist(a, b):
        ab = b - a
        t = np.clip(((pts - a) @ ab) / (ab @ ab), 0.0, 1.0)
        return np.hypot(*(pts - (a + t[:, None] * ab)).T)

    dists = np.stack([seg_dist(quad[i], quad[(i + 1) % 4]) for i in range(4)])
    side = dists.argmin(axis=0)
    near_corner = np.min([np.hypot(*(pts - q).T) for q in quad], axis=0) < CORNER_MARGIN_PX
    rng = np.random.default_rng(0)
    lines = []
    for i in range(4):
        sp = pts[(side == i) & ~near_corner]
        if len(sp) < 2:
            return None
        line = _ransac_line(sp, rng, np)
        if line is None:
            return None
        lines.append(line)
    out = []
    for i in range(4):
        pt = _intersect(lines[(i - 1) % 4], lines[i], np)
        if pt is None:
            return None
        out.append(pt)
    return np.asarray(out, dtype=np.float32)


def _query_points(quad, ring, np):
    """Points to track, from frame 0 corners ``quad`` (float [4, 2], clockwise).

    Ring: ``ring`` points on a band just outside the quad (bezel and surroundings). They stay
    visible when a hand or finger covers the screen content and they carry the plane's motion
    because bezel and screen share one plane. Grid: points inside the quad. A textured screen
    tracks well, and they keep the fit stable when the bezel is plain or partly out of frame.
    """
    area = abs(_signed_area(quad))
    c = quad.mean(axis=0)
    off = RING_OFFSET * math.sqrt(area)
    edges = np.roll(quad, -1, axis=0) - quad
    lens = np.hypot(edges[:, 0], edges[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(lens)])
    pts = []
    for s in (np.arange(ring) + 0.5) * cum[-1] / ring:
        i = min(int(np.searchsorted(cum, s, side="right") - 1), 3)
        p = quad[i] + edges[i] * ((s - cum[i]) / lens[i])
        d = p - c
        pts.append(p + d / max(np.hypot(*d), 1e-9) * off)
    u = np.linspace(GRID_INSET, 1.0 - GRID_INSET, GRID_N)
    for v in u:
        for w in u:
            top = quad[0] + (quad[1] - quad[0]) * w
            bot = quad[3] + (quad[2] - quad[3]) * w
            pts.append(top + (bot - top) * v)
    return np.asarray(pts, dtype=np.float64)


def _signed_area(quad):
    x, y = quad[:, 0], quad[:, 1]
    return 0.5 * float((x * (y.take([1, 2, 3, 0])) - x.take([1, 2, 3, 0]) * y).sum())


def corners_track(frames, init_corners, ring=24, fps=30.0, min_cutoff=1.0, beta=0.5, d_cutoff=1.0,
                  return_visible=False):
    """Follow a planar screen through RGB uint8 ``frames`` [T, H, W, 3].

    ``init_corners`` is float [4, 2], clockwise from top-left, at frame 0. Returns
    (corners float64 [T, 4, 2], inlier ratio float64 [T]). Per frame a RANSAC homography maps the
    frame-0 points to their tracked positions using only visible points; the corners follow it.
    With fewer than 4 visible points the ratio is 0 and the previous homography is kept.
    The corners are smoothed with One-Euro; the defaults favour low lag over low jitter.
    With ``return_visible`` a third value, the tracker's visibility bool [T, N], follows; that is
    what ``check_track`` needs.
    """
    cv2, np = _deps()
    quad = np.asarray(init_corners, dtype=np.float64)
    if quad.shape != (4, 2):
        raise ValueError("init_corners must be [4, 2]")
    area = _signed_area(quad)
    if abs(area) < MIN_QUAD_AREA_PX2:
        raise ValueError(f"init_corners are degenerate (area {abs(area):.0f} px2 < {MIN_QUAD_AREA_PX2:.0f})")
    if area < 0:
        raise ValueError("init_corners must run clockwise from top-left")
    frames = np.asarray(frames)
    n_frames, h, w = frames.shape[:3]

    pts = _query_points(quad, ring, np)
    inside = (pts[:, 0] >= 0) & (pts[:, 0] <= w - 1) & (pts[:, 1] >= 0) & (pts[:, 1] <= h - 1)
    pts = pts[inside]
    if len(pts) < 4:
        raise ValueError("fewer than 4 tracking points fall inside the frame")

    from . import pointtrack
    queries = np.column_stack([np.zeros(len(pts)), pts])
    tracks, visible = pointtrack.track(frames, queries)

    smooth = OneEuro(fps, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
    out = np.zeros((n_frames, 4, 2))
    ratio = np.zeros(n_frames)
    hom = np.eye(3)
    for t in range(n_frames):
        vis = np.asarray(visible[t], dtype=bool)
        if vis.sum() >= 4:
            m, mask = cv2.findHomography(pts[vis], np.asarray(tracks[t], np.float64)[vis],
                                         cv2.RANSAC, HOMOGRAPHY_TOL_PX)
            if m is not None:
                hom = m
                ratio[t] = float(mask.sum()) / float(vis.sum())
        raw = cv2.perspectiveTransform(quad.reshape(-1, 1, 2), hom).reshape(4, 2)
        out[t] = smooth(raw)
    if return_visible:
        return out, ratio, np.asarray(visible, dtype=bool)
    return out, ratio


def check_track(corners, inliers, visible, fps, diag):
    """Raise ``Refused`` when a track is not trustworthy; return None when it is.

    ``corners`` [T, 4, 2] (after smoothing), ``inliers`` [T], ``visible`` [T, N] bool, ``diag`` the
    screen diagonal in px. Rules: more than 30% of points hidden for 0.5 s or longer; a corner
    moving more than 8% of ``diag`` between two frames; an inlier ratio under 0.5.
    """
    _, np = _deps()
    corners = np.asarray(corners, dtype=np.float64)
    inliers = np.asarray(inliers, dtype=np.float64)
    visible = np.asarray(visible, dtype=bool)
    n_pts = visible.shape[1]

    lost = (~visible).sum(axis=1) * 10 > LOST_POINT_SHARE * 10 * n_pts
    need = LOST_SECONDS * fps - 1e-9
    t = 0
    while t < len(lost):
        if not lost[t]:
            t += 1
            continue
        end = t
        while end + 1 < len(lost) and lost[end + 1]:
            end += 1
        if end - t + 1 >= need:
            pct = round(100.0 * float((~visible[t:end + 1]).sum(axis=1).max()) / n_pts)
            raise Refused(f"track lost on frames {t}-{end} ({pct}% points hidden)")
        t = end + 1

    if len(corners) > 1:
        step = np.linalg.norm(np.diff(corners, axis=0), axis=2).max(axis=1)
        bad = np.nonzero(step > JUMP_DIAG_SHARE * diag)[0]
        if len(bad):
            raise Refused(f"corner jump {step[bad[0]]:.1f} px at frame {bad[0] + 1}")

    weak = np.nonzero(inliers < MIN_INLIER_RATIO)[0]
    if len(weak):
        raise Refused(f"homography unstable at frame {weak[0]} (inliers {inliers[weak[0]]:.2f})")


def _quad_size(c, np):
    w = (np.hypot(*(c[1] - c[0])) + np.hypot(*(c[2] - c[3]))) / 2.0
    h = (np.hypot(*(c[3] - c[0])) + np.hypot(*(c[2] - c[1]))) / 2.0
    return max(float(w), 1.0), max(float(h), 1.0)


def _split_panel(panel, np):
    """(BGR float32 [h, w, 3], alpha float32 [h, w] in 0..1) from a BGR or BGRA uint8 panel."""
    panel = np.asarray(panel)
    if panel.ndim == 2:
        panel = np.dstack([panel] * 3)
    if panel.ndim != 3 or panel.shape[2] not in (3, 4):
        raise ValueError(f"panel must be [h, w, 3 or 4], got shape {panel.shape}")
    bgr = panel[..., :3].astype(np.float32)
    alpha = (panel[..., 3].astype(np.float32) / 255.0 if panel.shape[2] == 4
             else np.ones(panel.shape[:2], np.float32))
    return bgr, alpha


def _letterbox(bgr, alpha, qw, qh, np):
    """Pad with opaque black so the panel keeps its shape inside a canvas with the quad's aspect.
    Within ASPECT_TOL of the quad's aspect the panel is left alone (the warp stretches it)."""
    ph, pw = bgr.shape[:2]
    qa, pa = qw / qh, pw / ph
    if abs(pa / qa - 1.0) <= ASPECT_TOL:
        return bgr, alpha
    if pa > qa:
        cw, ch = pw, int(round(pw / qa))
    else:
        cw, ch = int(round(ph * qa)), ph
    canvas = np.zeros((ch, cw, 3), np.float32)
    calpha = np.ones((ch, cw), np.float32)
    y0, x0 = (ch - ph) // 2, (cw - pw) // 2
    canvas[y0:y0 + ph, x0:x0 + pw] = bgr
    calpha[y0:y0 + ph, x0:x0 + pw] = alpha
    return canvas, calpha


def _motion_kernel(corners, prev, cv2, np):
    """Line kernel as long as the mean corner displacement, along its principal direction; None
    when the quad moved less than 1 px."""
    disp = corners - prev
    length = float(np.linalg.norm(disp, axis=1).mean())
    if length < 1.0:
        return None
    _, _, vt = np.linalg.svd(disp, full_matrices=False)
    d = vt[0]
    size = max(3, int(round(length)) | 1)
    k = np.zeros((size, size), np.float32)
    r = (size - 1) / 2.0
    c = (size - 1) // 2
    p0 = (int(round(c - d[0] * r)), int(round(c - d[1] * r)))
    p1 = (int(round(c + d[0] * r)), int(round(c + d[1] * r)))
    cv2.line(k, p0, p1, 1.0, 1)
    return k / k.sum()


def composite(frame, panel, corners, occluder=None, prev_corners=None, glass=0.08):
    """Put ``panel`` on the screen quad ``corners`` of ``frame`` (BGR uint8) and return the frame.

    ``panel`` is BGR or BGRA uint8; alpha is respected, so a transparent hole shows the frame.
    A panel whose aspect differs from the quad's by more than 2% is letterboxed with black bars,
    never stretched. Steps: perspective warp; luminance gain so the panel's mean luminance equals
    the 90th percentile luminance of the original screen region (gain clamped to 0.6-1.4, the
    region excludes ``occluder``); motion blur on the warped panel layer only, a line kernel as
    long as the mean corner displacement from ``prev_corners`` (none when None) and along its
    principal direction; a 1.5 px feathered quad edge; ``glass`` times the original's high
    frequencies (original minus its gaussian blur, sigma 6) added on top inside the quad;
    ``occluder`` (bool [H, W]) pixels are copied from ``frame`` exactly.
    """
    cv2, np = _deps()
    frame = np.asarray(frame)
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError("frame must be a BGR uint8 [H, W, 3] array")
    quad = np.asarray(corners, dtype=np.float64)
    if quad.shape != (4, 2):
        raise ValueError("corners must be [4, 2]")
    h, w = frame.shape[:2]
    occ = None
    if occluder is not None:
        occ = np.asarray(occluder, dtype=bool)
        if occ.shape != (h, w):
            raise ValueError(f"occluder must be [{h}, {w}], got {occ.shape}")

    bgr, alpha = _split_panel(panel, np)
    covered = alpha > 0.5
    lum_w = np.array([0.114, 0.587, 0.299], np.float32)
    panel_lum = float(((bgr @ lum_w)[covered]).mean()) if covered.any() else 0.0
    qw, qh = _quad_size(quad, np)
    bgr, alpha = _letterbox(bgr, alpha, qw, qh, np)

    ch, cw = bgr.shape[:2]
    src = np.float32([[0, 0], [cw - 1, 0], [cw - 1, ch - 1], [0, ch - 1]])
    m = cv2.getPerspectiveTransform(src, quad.astype(np.float32))
    stack = np.dstack([bgr * alpha[..., None], alpha])
    warped = cv2.warpPerspective(stack, m, (w, h), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    w_alpha = warped[..., 3]

    premult = warped[..., :3]
    if prev_corners is not None:
        prev = np.asarray(prev_corners, dtype=np.float64)
        if prev.shape != (4, 2):
            raise ValueError("prev_corners must be [4, 2]")
        kernel = _motion_kernel(quad, prev, cv2, np)
        if kernel is not None:
            blurred = cv2.filter2D(warped, -1, kernel, borderType=cv2.BORDER_CONSTANT)
            premult, b_alpha = blurred[..., :3], blurred[..., 3]
        else:
            b_alpha = w_alpha
    else:
        b_alpha = w_alpha
    layer = premult / np.maximum(b_alpha, 1e-4)[..., None]

    region = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(region, np.round(quad).astype(np.int32), 255)
    inside = cv2.erode(region, np.ones((7, 7), np.uint8)) > 0
    if occ is not None:
        inside &= ~occ
    if inside.any() and panel_lum > 1.0:
        target = float(np.percentile((frame.astype(np.float32) @ lum_w)[inside], 90))
        gain = min(max(target / panel_lum, GAIN_RANGE[0]), GAIN_RANGE[1])
        layer = layer * gain

    feather = np.zeros((h, w), np.float32)
    cv2.fillConvexPoly(feather, np.round(quad * 16).astype(np.int32), 1.0, cv2.LINE_AA, shift=4)
    feather = cv2.GaussianBlur(feather, (0, 0), FEATHER_SIGMA)
    a = (w_alpha * feather)[..., None]

    orig = frame.astype(np.float32)
    out = orig * (1.0 - a) + layer * a
    if glass > 0:
        resid = orig - cv2.GaussianBlur(orig, (0, 0), 6)
        out = out + glass * resid * a
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    if occ is not None:
        out[occ] = frame[occ]
    return out


def _decode(path, width, height, fps=None):
    """All frames of a video as BGR uint8 [T, H, W, 3] through an ffmpeg rawvideo pipe."""
    _, np = _deps()
    from . import ff
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-an"]
    if fps:
        cmd += ["-vf", f"fps={fps}"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    data = ff.run_bytes(cmd)
    size = width * height * 3
    n = len(data) // size
    if n == 0:
        raise RuntimeError(f"no frames decoded from {path}")
    return np.frombuffer(data, np.uint8, n * size).reshape(n, height, width, 3)


def _load_panel(panel, width, height, fps):
    """List-like of panel frames: one held image for a still, decoded frames for a video."""
    cv2, np = _deps()
    from . import ff
    path = str(panel)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"panel not found: {path}")
    if path.lower().endswith(IMAGE_SUFFIXES):
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"panel is not a readable image: {path}")
        return [img]
    info = ff.probe(path)["video"]
    if not info:
        raise ValueError(f"panel has no video stream: {path}")
    return _decode(path, info["width"], info["height"], fps)


def _green_corners(frames, fps, np, cv2):
    """Per-frame smoothed green-key corners [T, 4, 2] and the number of frames without a key."""
    raw = [corners_green(f) for f in frames]
    missing = sum(1 for c in raw if c is None)
    if missing == len(raw) or missing > GREEN_MISSING_MAX * len(raw):
        raise Refused(f"green key missing on {missing} frames")
    first = next(c for c in raw if c is not None)
    smooth = OneEuro(fps, min_cutoff=1.0, beta=0.5)
    out, last = [], first
    for c in raw:
        last = last if c is None else c
        out.append(smooth(last))
    return np.stack(out), missing


def _green_occluders(frames, corners, hue=(40, 85), sat_min=80, val_min=60):
    """Per-frame bool masks: non-green pixels inside the quad, read OCCLUDER_ERODE_PX inside it."""
    cv2, np = _deps()
    k = 2 * OCCLUDER_ERODE_PX + 1
    dil = np.ones((3, 3), np.uint8)
    out = np.zeros(frames.shape[:3], bool)
    for t, f in enumerate(frames):
        quad = np.zeros(f.shape[:2], np.uint8)
        cv2.fillConvexPoly(quad, np.round(corners[t]).astype(np.int32), 255)
        quad = cv2.erode(quad, np.ones((k, k), np.uint8))
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        key = cv2.inRange(hsv, (hue[0], sat_min, val_min), (hue[1], 255, 255))
        out[t] = cv2.dilate(((key == 0) & (quad > 0)).astype(np.uint8), dil) > 0
    return out


def _encode(frames_iter, clip, out, width, height, fps):
    from . import ff
    ff.ensure_parent(out)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
           "-r", f"{fps:.6f}", "-i", "-", "-i", str(clip), "-map", "0:v", "-map", "1:a?",
           "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "15",
           "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)]
    with tempfile.TemporaryFile() as errf:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errf)
        except FileNotFoundError:
            raise ff.FFMissing("ffmpeg not found on PATH") from None
        try:
            for f in frames_iter:
                proc.stdin.write(f.tobytes())
        except BrokenPipeError:
            pass
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
        rc = proc.wait()
        errf.seek(0)
        err = errf.read().decode(errors="replace")
    if rc != 0:
        raise ff.FFError(f"ffmpeg failed ({rc}):\n{err.strip()[-900:]}")


def insert(clip, panel, out, mode, seed=None, corners=None, occluder_point=None, qa_dir=None):
    """Replace the screen in ``clip`` with ``panel`` (PNG held, or mp4 looped / truncated) -> ``out``.

    ``mode="green"``: corners from the green key per frame, a frame without a key holds the
    previous corners (more than 5% of them refuses), smoothed with One-Euro; the occluder is
    whatever is not green inside the quad. ``mode="track"``: ``corners`` (4x2, clockwise from
    top-left, at frame 0) are followed with ``corners_track`` and vetted by ``check_track``; the
    occluder is the SAM 2.1 mask of ``occluder_point`` ([x, y] at frame 0) when given, else none.
    The clip is decoded whole into memory (BGR uint8), fine for the short clips this serves.
    ``seed`` is accepted for the CLI's contract and unused: nothing here is random.
    The output is H.264 yuv420p crf 15, the clip's audio copied, the same number of frames.
    Returns ``{"frames", "mode", "min_inlier", "max_jump_px", "lost_frames"}``.
    """
    cv2, np = _deps()
    from . import ff
    if mode not in ("green", "track"):
        raise ValueError(f"mode must be green or track, got {mode!r}")
    info = ff.probe(str(clip))["video"]
    if not info:
        raise ValueError(f"clip has no video stream: {clip}")
    width, height, fps = info["width"], info["height"], info["fps"] or 30.0
    frames = _decode(str(clip), width, height)
    n = len(frames)
    pframes = _load_panel(panel, width, height, fps)

    if mode == "green":
        quads, missing = _green_corners(frames, fps, np, cv2)
        occ = _green_occluders(frames, quads)
        min_inlier, lost = 1.0, missing
    else:
        if corners is None:
            raise ValueError("track mode needs corners (4x2, clockwise from top-left, at frame 0)")
        init = np.asarray(corners, dtype=np.float64).reshape(4, 2)
        rgb = np.ascontiguousarray(frames[..., ::-1])
        quads, inl, vis = corners_track(rgb, init, fps=fps, return_visible=True)
        diag = float(np.hypot(*(init[0] - init[2])))
        check_track(quads, inl, vis, fps, diag)
        min_inlier = float(inl.min())
        lost = int(((~vis).sum(axis=1) * 10 > LOST_POINT_SHARE * 10 * vis.shape[1]).sum())
        occ = None
        if occluder_point is not None:
            from . import segment
            occ = segment.masks(rgb, 0, points=[list(occluder_point)])

    jump = float(np.linalg.norm(np.diff(quads, axis=0), axis=2).max()) if n > 1 else 0.0

    def rendered():
        for t in range(n):
            yield composite(frames[t], pframes[t % len(pframes)], quads[t],
                            occluder=None if occ is None else occ[t],
                            prev_corners=quads[t - 1] if t else None)

    _encode(rendered(), clip, out, width, height, fps)
    if qa_dir:
        from . import sheet
        os.makedirs(qa_dir, exist_ok=True)
        sheet.contact_sheet(str(out), os.path.join(str(qa_dir), "qa-screen.jpg"))
    return {"frames": n, "mode": mode, "min_inlier": min_inlier, "max_jump_px": jump, "lost_frames": lost}
