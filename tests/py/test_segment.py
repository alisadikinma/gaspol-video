import importlib.util
import unittest

HAS_NUMPY = importlib.util.find_spec("numpy") is not None


def _ml_ready():
    if not (HAS_NUMPY and importlib.util.find_spec("torch") and importlib.util.find_spec("sam2")):
        return False
    from tools.vidkit import ml
    try:
        ml.weight("sam2.1_hiera_small.pt")
    except ml.MLMissing:
        return False
    return True


needs_numpy = unittest.skipUnless(HAS_NUMPY, "numpy not importable on this interpreter")
needs_ml = unittest.skipUnless(_ml_ready(), "torch, sam2 or SAM 2.1 weights missing")

W, H, T, R = 320, 240, 24, 30


def _disc(cx, cy, w=W, h=H, r=R):
    import numpy as np
    yy, xx = np.mgrid[:h, :w]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r


def _centres(n=T, x0=60, speed=4, y=120):
    return [(x0 + speed * t, y) for t in range(n)]


def _clip(centres, second=None, w=W, h=H):
    """Seeded noisy grey background, a red disc at `centres`, optional static blue disc `second`."""
    import numpy as np
    rng = np.random.default_rng(11)
    frames = []
    for cx, cy in centres:
        noise = rng.integers(-12, 13, (h, w, 1))
        frame = np.clip(128 + noise, 0, 255).repeat(3, axis=2).astype(np.uint8)
        if second is not None:
            frame[_disc(*second, w=w, h=h)] = (0, 0, 255)
        frame[_disc(cx, cy, w=w, h=h)] = (255, 0, 0)
        frames.append(frame)
    return np.stack(frames)


def _iou(a, b):
    union = (a | b).sum()
    return 1.0 if union == 0 else (a & b).sum() / union


def _ious(masks, centres, w=W, h=H):
    return [_iou(masks[t], _disc(cx, cy, w=w, h=h)) for t, (cx, cy) in enumerate(centres)]


@needs_numpy
@needs_ml
class MaskAccuracy(unittest.TestCase):
    def test_point_on_disc(self):
        import numpy as np
        from tools.vidkit import segment
        centres = _centres()
        masks = segment.masks(_clip(centres), 0, points=[list(centres[0])])
        ious = _ious(masks, centres)
        print(f"\npoint: min IoU={min(ious):.3f}")
        self.assertEqual(masks.shape, (T, H, W))
        self.assertEqual(masks.dtype, np.bool_)
        self.assertGreaterEqual(min(ious), 0.9)

    def test_box_on_disc(self):
        from tools.vidkit import segment
        centres = _centres()
        cx, cy = centres[0]
        masks = segment.masks(_clip(centres), 0, box=[cx - R, cy - R, cx + R, cy + R])
        ious = _ious(masks, centres)
        print(f"\nbox: min IoU={min(ious):.3f}")
        self.assertGreaterEqual(min(ious), 0.9)

    def test_negative_point_excludes_second_disc(self):
        import numpy as np
        from tools.vidkit import segment
        centres = _centres()
        second = (250, 60)
        frames = _clip(centres, second=second)
        # box around both discs would include the blue one; the negative point removes it
        masks = segment.masks(frames, 0, points=[list(centres[0]), list(second)], labels=[1, 0])
        blue = _disc(*second)
        leak = np.array([(m & blue).sum() / blue.sum() for m in masks])
        ious = _ious(masks, centres)
        print(f"\nnegative: max blue leak={leak.max():.4f} min IoU={min(ious):.3f}")
        self.assertLess(leak.max(), 0.02)
        self.assertGreaterEqual(min(ious), 0.9)

    def test_prompt_mid_clip_covers_earlier_frames(self):
        from tools.vidkit import segment
        centres = _centres()
        masks = segment.masks(_clip(centres), 12, points=[list(centres[12])])
        ious = _ious(masks, centres)
        print(f"\nmid-clip: before min IoU={min(ious[:12]):.3f} after min IoU={min(ious[12:]):.3f}")
        self.assertGreaterEqual(min(ious[:12]), 0.9)
        self.assertGreaterEqual(min(ious[12:]), 0.9)

    def test_disc_leaves_frame(self):
        from tools.vidkit import segment
        centres = _centres(x0=250, speed=12)
        masks = segment.masks(_clip(centres), 0, points=[list(centres[0])])
        areas = masks.reshape(T, -1).sum(axis=1)
        print(f"\nleaves: areas of last 8 frames={areas[-8:].tolist()}")
        self.assertEqual(masks.shape, (T, H, W))
        self.assertEqual(int(areas[-8:].max()), 0)

    def test_single_frame(self):
        from tools.vidkit import segment
        centres = _centres(n=1)
        masks = segment.masks(_clip(centres), 0, points=[list(centres[0])])
        iou = _ious(masks, centres)[0]
        print(f"\nT=1: IoU={iou:.3f}")
        self.assertEqual(masks.shape, (1, H, W))
        self.assertGreaterEqual(iou, 0.9)


@needs_numpy
class MaskValidation(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.frames = np.zeros((4, 24, 32, 3), np.uint8)

    def _fails(self, frames=None, idx=0, **kw):
        from tools.vidkit import segment
        with self.assertRaises(ValueError):
            segment.masks(self.frames if frames is None else frames, idx, **kw)

    def test_no_prompt(self):
        self._fails()
        self._fails(points=[], labels=[])

    def test_labels_mismatch(self):
        self._fails(points=[[5, 5], [6, 6]], labels=[1])

    def test_label_value(self):
        self._fails(points=[[5, 5]], labels=[2])

    def test_point_outside(self):
        for p in ([-1, 5], [32, 5], [5, 24], [5, -0.5]):
            self._fails(points=[p])

    def test_box_bad(self):
        for b in ([0, 0, 40, 10], [-5, 0, 10, 10], [10, 0, 5, 10], [0, 10, 10, 2], [0, 0, 5]):
            self._fails(box=b)

    def test_frame_idx(self):
        for i in (4, -1):
            self._fails(idx=i, points=[[5, 5]])

    def test_wrong_dims(self):
        import numpy as np
        self._fails(frames=self.frames[0], points=[[5, 5]])
        self._fails(frames=self.frames[..., :2], points=[[5, 5]])
        self._fails(frames=self.frames.astype(np.float32), points=[[5, 5]])
        self._fails(frames=self.frames[:0], points=[[5, 5]])

    def test_nan_point(self):
        self._fails(points=[[float("nan"), 5]])


class ImportSafe(unittest.TestCase):
    def test_module_imports_without_ml_stack(self):
        from tools.vidkit import segment
        self.assertTrue(callable(segment.masks))


@needs_numpy
class MissingTorchTest(unittest.TestCase):
    def test_valid_inputs_without_torch_raise_mlmissing(self):
        import os
        import sys
        from unittest import mock
        import numpy as np
        from tools.vidkit import ml, segment
        frames = np.zeros((2, 16, 16, 3), np.uint8)
        env = {"GASPOL_VIDEO_ML_REEXEC": "1"}     # no re-exec into venv-ml: it would replace this process
        with mock.patch.dict(sys.modules, {"torch": None}), mock.patch.dict(os.environ, env):
            os.environ.pop("GASPOL_ML_DEVICE", None)
            with self.assertRaises(ml.MLMissing):
                segment.masks(frames, 0, points=[[4, 4]])


if __name__ == "__main__":
    unittest.main()
