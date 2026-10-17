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


def corners_track(frames, init_corners, ring=24, fps=30.0, min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
    """Follow a planar screen through RGB uint8 ``frames`` [T, H, W, 3].

    ``init_corners`` is float [4, 2], clockwise from top-left, at frame 0. Returns
    (corners float64 [T, 4, 2], inlier ratio float64 [T]). Per frame a RANSAC homography maps the
    frame-0 points to their tracked positions using only visible points; the corners follow it.
    With fewer than 4 visible points the ratio is 0 and the previous homography is kept.
    The corners are smoothed with One-Euro; the defaults favour low lag over low jitter.
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
