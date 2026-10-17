"""Occlusion-aware point tracking through a clip with TAPNext++.

Needs the ML venv (``tools/setup.sh --ml``): torch, tapnet and the TAPNext++ checkpoint. Every
heavy import is lazy, so importing this module works on any interpreter; ``track`` raises
``ml.MLMissing`` naming the fix when the stack is absent.

    tracks, visible = track(frames, queries)

``frames`` is a uint8 array [T, H, W, 3] (RGB), ``queries`` a float array [N, 3] of (t, x, y) in
input pixels. ``tracks`` is [T, N, 2] (x, y) in input pixels and ``visible`` is [T, N] bool.
"""
import os
import sys
import time

from . import ml

_models = {}


def _load(device):
    model = _models.get(device)
    if model is None:
        ml.require()
        try:
            from tapnet.tapnextpp.votsp2026.model import TAPNextPP
        except ImportError as exc:
            raise ml.MLMissing(f"missing tapnet ({exc}): {ml.FIX}") from None
        model = TAPNextPP.from_checkpoint(str(ml.weight("tapnextpp_ckpt.pt")), device=device)
        _models[device] = model
    return model


def _validate(frames, queries):
    import numpy as np
    frames = np.asarray(frames)
    queries = np.asarray(queries, dtype=np.float32)
    if frames.ndim != 4 or frames.shape[3] != 3:
        raise ValueError(f"frames must be [T, H, W, 3], got shape {frames.shape}")
    if frames.dtype != np.uint8:
        raise ValueError(f"frames must be uint8, got {frames.dtype}")
    if frames.shape[0] == 0:
        raise ValueError("frames is empty (T == 0)")
    if queries.ndim != 2 or queries.shape[1] != 3:
        raise ValueError(f"queries must be [N, 3] rows of (t, x, y), got shape {queries.shape}")
    if queries.shape[0] == 0:
        raise ValueError("queries is empty (N == 0)")
    if not np.isfinite(queries).all():
        raise ValueError("queries contain NaN or inf")
    n_frames, height, width = frames.shape[:3]
    for row, (t, x, y) in enumerate(queries):
        if t != int(t) or not 0 <= t < n_frames:
            raise ValueError(f"query {row}: t={t} outside 0..{n_frames - 1}")
        if not (0 <= x <= width - 1 and 0 <= y <= height - 1):
            raise ValueError(f"query {row}: point ({x}, {y}) outside the {width}x{height} frame")
    return frames, queries


def _run(model, bgr, points):
    """Track `points` [Q, 2] from the first of `bgr` forward; return pos [len, Q, 2], vis [len, Q]."""
    import numpy as np
    pos, vis, state = model.track_frame(bgr[0], points)
    out_pos, out_vis = [np.asarray(pos, np.float32)], [np.asarray(vis, bool)]
    for frame in bgr[1:]:
        pos, vis, state = model.track_frame(frame, state=state)
        out_pos.append(np.asarray(pos, np.float32))
        out_vis.append(np.asarray(vis, bool))
    return np.stack(out_pos), np.stack(out_vis)


def track(frames, queries):
    frames, queries = _validate(frames, queries)
    import numpy as np
    device = ml.device()
    model = _load(device)
    started = time.time()

    n_frames = frames.shape[0]
    bgr = [np.ascontiguousarray(frame[..., ::-1]) for frame in frames]
    tracks = np.zeros((n_frames, len(queries), 2), np.float32)
    visible = np.zeros((n_frames, len(queries)), bool)
    processed = 0

    for t in np.unique(queries[:, 0]).astype(int):
        idx = np.flatnonzero(queries[:, 0] == t)
        points = np.ascontiguousarray(queries[idx, 1:3])
        fwd_pos, fwd_vis = _run(model, bgr[t:], points)
        tracks[t:, idx], visible[t:, idx] = fwd_pos, fwd_vis
        processed += n_frames - t
        if t > 0:
            back_pos, back_vis = _run(model, bgr[t::-1], points)
            tracks[:t, idx] = back_pos[:0:-1]
            visible[:t, idx] = back_vis[:0:-1]
            processed += t + 1
        tracks[t, idx] = points
        visible[t, idx] = True

    if os.environ.get("GASPOL_ML_DEBUG") == "1":
        elapsed = max(time.time() - started, 1e-9)
        print(f"pointtrack: device={device} frames={processed} fps={processed / elapsed:.1f}",
              file=sys.stderr)
    return tracks, visible
