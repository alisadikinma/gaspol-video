"""Screen corners for the screen-insert workflow.

A green-screen clip gives exact corners: key the green, take the largest blob, fit one line per
side and intersect them. A finger or hand over one edge only adds outlier points to that side's
line fit (RANSAC drops them), so the corner does not move. Contrast with ``tools/track_screen.py``,
which flood-fills from a seed and so follows whatever occludes the edge.

Also holds ``OneEuro``, the One-Euro low-pass filter (Casiez et al. 2012) used to smooth corner
tracks. ``cv2`` and ``numpy`` are imported lazily so importing this module works on a bare python3.
"""
import math

MIN_SCREEN_WIDTH_PX = 40
RANSAC_TOL_PX = 1.5
RANSAC_ITERS = 200
CORNER_MARGIN_PX = 6.0


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
