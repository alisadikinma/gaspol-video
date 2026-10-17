"""Mask an object through a clip from one click or box with SAM 2.1.

Needs the ML venv (``tools/setup.sh --ml``): torch, sam2 and the SAM 2.1 small checkpoint. Every
heavy import is lazy, so importing this module works on any interpreter; ``masks`` raises
``ml.MLMissing`` naming the fix when the stack is absent.

    mask = masks(frames, frame_idx, points=[[x, y]], labels=[1], box=[x0, y0, x1, y1])

``frames`` is a uint8 array [T, H, W, 3] (RGB). The prompt is given on frame ``frame_idx``;
``points`` are (x, y) in pixels with ``labels`` 1 (include) or 0 (exclude), ``box`` is
(x0, y0, x1, y1). Returns a bool array [T, H, W]. A frame where the object is gone is all False.
"""
import os
import sys
import tempfile
import time
import warnings

from . import ml

CONFIG = "configs/sam2.1/sam2.1_hiera_s.yaml"

_models = {}


def _load(device):
    model = _models.get(device)
    if model is None:
        ml.require()
        weights = ml.weight("sam2.1_hiera_small.pt")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*cannot import name '_C'.*")
            try:
                from sam2.build_sam import build_sam2_video_predictor
            except ImportError as exc:
                raise ml.MLMissing(f"missing sam2 ({exc}): {ml.FIX}") from None
            model = build_sam2_video_predictor(CONFIG, str(weights), device=device)
        _models[device] = model
    return model


def _validate(frames, frame_idx, points, labels, box):
    import numpy as np
    frames = np.asarray(frames)
    if frames.ndim != 4 or frames.shape[3] != 3:
        raise ValueError(f"frames must be [T, H, W, 3], got shape {frames.shape}")
    if frames.dtype != np.uint8:
        raise ValueError(f"frames must be uint8, got {frames.dtype}")
    n_frames, height, width = frames.shape[:3]
    if n_frames == 0:
        raise ValueError("frames is empty (T == 0)")
    if frame_idx != int(frame_idx) or not 0 <= frame_idx < n_frames:
        raise ValueError(f"frame_idx {frame_idx} outside 0..{n_frames - 1}")

    has_points = points is not None and len(points) > 0
    if not has_points and box is None:
        raise ValueError("no prompt: give points or box")

    pts = lbl = None
    if has_points:
        pts = np.asarray(points, dtype=np.float32)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError(f"points must be [[x, y], ...], got shape {pts.shape}")
        if not np.isfinite(pts).all():
            raise ValueError("points contain NaN or inf")
        lbl = np.ones(len(pts), np.int32) if labels is None else np.asarray(labels)
        if lbl.shape != (len(pts),):
            raise ValueError(f"{len(pts)} points but labels shape {lbl.shape}")
        if not np.isin(lbl, (0, 1)).all():
            raise ValueError("labels must be 1 (include) or 0 (exclude)")
        lbl = lbl.astype(np.int32)
        for x, y in pts:
            if not (0 <= x <= width - 1 and 0 <= y <= height - 1):
                raise ValueError(f"point ({x}, {y}) outside the {width}x{height} frame")
    elif labels is not None and len(labels) > 0:
        raise ValueError("labels given without points")

    bx = None
    if box is not None:
        bx = np.asarray(box, dtype=np.float32)
        if bx.shape != (4,) or not np.isfinite(bx).all():
            raise ValueError(f"box must be [x0, y0, x1, y1], got {box!r}")
        x0, y0, x1, y1 = bx
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError(f"box {bx.tolist()} is inverted or outside the {width}x{height} frame")
    return frames, pts, lbl, bx


def _write_jpegs(frames, folder):
    import cv2
    for i, frame in enumerate(frames):
        ok = cv2.imwrite(os.path.join(folder, f"{i:05d}.jpg"), frame[..., ::-1],
                         [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError(f"could not write frame {i}")


def masks(frames, frame_idx, points=None, labels=None, box=None):
    frames, pts, lbl, bx = _validate(frames, frame_idx, points, labels, box)
    import numpy as np
    import torch
    device = ml.device()
    model = _load(device)
    started = time.time()
    n_frames, height, width = frames.shape[:3]
    out = np.zeros((n_frames, height, width), bool)
    processed = 0

    with tempfile.TemporaryDirectory() as folder, torch.inference_mode():
        _write_jpegs(frames, folder)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*cannot import name '_C'.*")
            state = model.init_state(video_path=folder)
            kwargs = {}
            if pts is not None:
                kwargs.update(points=pts, labels=lbl)
            if bx is not None:
                kwargs["box"] = bx
            model.add_new_points_or_box(state, frame_idx=int(frame_idx), obj_id=1, **kwargs)
            for idx, _ids, logits in model.propagate_in_video(state):
                out[idx] = (logits[0, 0] > 0).cpu().numpy()
                processed += 1
            if frame_idx > 0:
                for idx, _ids, logits in model.propagate_in_video(state, reverse=True):
                    out[idx] = (logits[0, 0] > 0).cpu().numpy()
                    processed += 1

    if os.environ.get("GASPOL_ML_DEBUG") == "1":
        elapsed = max(time.time() - started, 1e-9)
        areas = out.reshape(n_frames, -1).sum(axis=1)
        print(f"segment: device={device} frames={processed} fps={processed / elapsed:.1f} "
              f"area min={int(areas.min())} max={int(areas.max())}", file=sys.stderr)
    return out
