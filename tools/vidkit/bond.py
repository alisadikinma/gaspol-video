"""Bond a transparent print (logo, watermark) onto cloth in a presenter clip so it looks printed.

Needs ``cv2`` and ``numpy`` (the shared venv has them via mediapipe; ``tools/setup.sh``). Imported
lazily so the rest of vidkit stays stdlib-only.

What it does, per frame:
  1. Upscale to the working size (default 1080x1920).
  2. Track body motion: ECC affine against frame 0 over a chest ROI, skin and dark pixels masked
     out (hands move on their own). Implausible results (shift > 40 px, scale/rotation > 6 %)
     are rejected and the last good warp is kept; a 5-frame moving average removes shake.
  3. Displace the print by the cloth's brightness gradient so it follows the folds.
  4. Apply only on fabric (low saturation, bright) and multiply, so the print takes the cloth's
     light and shade instead of lying on top.
"""
import subprocess

MOTION_MAX_SHIFT_PX = 40      # at half resolution
MOTION_MAX_LINEAR = 0.06
FABRIC_SAT_MAX, FABRIC_VAL_MIN = 70, 105


def _deps():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("bond needs cv2 and numpy: run tools/setup.sh and use the venv python") from exc
    return cv2, np


def fabric_mask(frame_bgr):
    cv2, np = _deps()
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] < FABRIC_SAT_MAX) & (hsv[..., 2] > FABRIC_VAL_MIN)).astype(np.uint8) * 255
    m = cv2.erode(m, np.ones((5, 5), np.uint8))
    return cv2.GaussianBlur(m, (0, 0), 2.2).astype(np.float32) / 255.0


def bond_print(clip, out, print_png, cx, top, width, rot=-1.2, roi=(180, 900, 940, 1450),
               size=(1080, 1920), print_ref_width=800.0, design_width=700.0, opacity=0.92,
               start=0, frames=0, crf=15):
    """Return ``{"frames", "failed_tracks", "shift_x", "shift_y"}``.

    ``width`` is the design width in the same units as ``design_width`` (so 700 = the print at its
    natural scale); ``print_ref_width`` is the width the PNG was designed at.
    """
    cv2, np = _deps()
    W, H = size
    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    clips = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        clips.append(cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC))
    cap.release()
    clips = clips[start:]
    if frames:
        clips = clips[:frames]
    n = len(clips)
    if n == 0:
        raise RuntimeError(f"no frames read from {clip}")

    P = cv2.imread(str(print_png), cv2.IMREAD_UNCHANGED)
    if P is None or P.ndim != 3 or P.shape[2] != 4:
        raise RuntimeError(f"{print_png} must be an RGBA png")
    pw = width * print_ref_width / design_width
    ph = pw * P.shape[0] / P.shape[1]
    P = cv2.resize(P, (int(round(pw)), int(round(ph))), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((H, W, 4), np.uint8)
    x0, y0 = int(round(cx - pw / 2)), int(round(top))
    canvas[y0:y0 + P.shape[0], x0:x0 + P.shape[1]] = P
    R = cv2.getRotationMatrix2D((cx, top + ph / 2), rot, 1.0)
    canvas = cv2.warpAffine(canvas, R, (W, H), flags=cv2.INTER_CUBIC)

    hw, hh = W // 2, H // 2
    small = [cv2.GaussianBlur(cv2.cvtColor(cv2.resize(f, (hw, hh)), cv2.COLOR_BGR2GRAY), (0, 0), 1.6)
             for f in clips]
    tmpl = small[0].astype(np.float32)
    mask = np.zeros(tmpl.shape, np.uint8)
    rx0, ry0, rx1, ry1 = roi
    mask[ry0 // 2:ry1 // 2, rx0 // 2:rx1 // 2] = 255
    hsv0 = cv2.cvtColor(cv2.resize(clips[0], (hw, hh)), cv2.COLOR_BGR2HSV)
    mask[(hsv0[..., 1] >= FABRIC_SAT_MAX) | (hsv0[..., 2] <= FABRIC_VAL_MIN)] = 0

    eye = np.eye(2, 3, dtype=np.float32)
    cur, warps, failed = eye.copy(), [eye.copy()], 0
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)
    for t in range(1, n):
        cand = cur.copy()
        try:
            _, cand = cv2.findTransformECC(tmpl, small[t].astype(np.float32), cand, cv2.MOTION_AFFINE,
                                           crit, mask, 5)
        except cv2.error:
            cand = None
        if (cand is None or not np.all(np.isfinite(cand))
                or np.abs(cand[:, :2] - eye[:, :2]).max() > MOTION_MAX_LINEAR
                or np.abs(cand[:, 2]).max() > MOTION_MAX_SHIFT_PX):
            failed += 1
        else:
            cur = cand
        full = cur.copy()
        full[:, 2] *= 2.0
        warps.append(full)
    arr = np.stack(warps)
    pad = np.pad(arr, ((2, 2), (0, 0), (0, 0)), mode="edge")
    arr = np.stack([pad[i:i + 5].mean(axis=0) for i in range(n)])

    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", f"{fps}", "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
         "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    for t, frame in enumerate(clips):
        layer = cv2.warpAffine(canvas, arr[t], (W, H), flags=cv2.INTER_CUBIC)
        g = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (0, 0), 7).astype(np.float32)
        dx = np.clip(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5) / 140.0, -3, 3)
        dy = np.clip(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5) / 140.0, -3, 3)
        layer = cv2.remap(layer, gx + dx, gy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(0, 0, 0, 0))
        alpha = layer[..., 3].astype(np.float32) / 255.0 * fabric_mask(frame) * opacity
        ink = layer[..., :3].astype(np.float32) / 255.0
        f32 = frame.astype(np.float32)
        mixed = f32 * (1 - alpha[..., None]) + f32 * ink * alpha[..., None]
        enc.stdin.write(np.clip(mixed, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("ffmpeg encoder failed")
    return {"frames": n, "failed_tracks": failed,
            "shift_x": (float(arr[:, 0, 2].min()), float(arr[:, 0, 2].max())),
            "shift_y": (float(arr[:, 1, 2].min()), float(arr[:, 1, 2].max()))}
