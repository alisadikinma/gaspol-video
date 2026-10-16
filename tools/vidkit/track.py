"""Smoothing for tracked screen boxes (pure Python, no OpenCV).

A brightest-blob tracker gives a stable box but a jittery angle: on a static monitor the angle
jumped from +8 to -6 degrees in four seconds, and the pasted panel visibly shook. Median-filter
the box, and when the target does not move, pin ONE angle for the whole clip.
"""
import statistics


def smooth_track(points, window=9, shrink=1.0, fixed_angle=True):
    """``points`` = ``[{"t","x","y","w","h","deg"}]``. Returns a new list.

    * x/y/w/h: moving median over ``window`` points (odd; wider than 5 survives a head briefly
      covering the screen edge).
    * ``deg``: the median of all points when ``fixed_angle`` (static target), else filtered too.
    * ``shrink`` < 1 contracts the box around its centre. The tracked blob is always a little
      larger than the real screen (the bezel glows), so without it the panel overhangs.
    """
    if window < 1 or window % 2 == 0:
        raise ValueError("window must be odd")
    half = window // 2

    def med(values, i):
        return statistics.median(values[max(0, i - half):min(len(values), i + half + 1)])

    cols = {k: [p[k] for p in points] for k in ("x", "y", "w", "h")}
    deg = [p["deg"] for p in points]
    pinned = round(statistics.median(deg), 2) if points and fixed_angle else None
    out = []
    for i, p in enumerate(points):
        b = {k: med(cols[k], i) for k in cols}
        if shrink != 1.0:
            b = {"x": b["x"] + b["w"] * (1 - shrink) / 2, "y": b["y"] + b["h"] * (1 - shrink) / 2,
                 "w": b["w"] * shrink, "h": b["h"] * shrink}
        d = pinned if fixed_angle else round(med(deg, i), 2)
        out.append({"t": p["t"], **{k: round(v, 1) for k, v in b.items()}, "deg": d})
    return out
