import importlib.util
import unittest

HAS_NUMPY = importlib.util.find_spec("numpy") is not None


def _ml_ready():
    if not (HAS_NUMPY and importlib.util.find_spec("torch") and importlib.util.find_spec("tapnet")):
        return False
    from tools.vidkit import ml
    try:
        ml.weight("tapnextpp_ckpt.pt")
    except ml.MLMissing:
        return False
    return True


needs_numpy = unittest.skipUnless(HAS_NUMPY, "numpy not importable on this interpreter")
needs_ml = unittest.skipUnless(_ml_ready(), "torch, tapnet or TAPNext++ weights missing")

W, H, T = 320, 240, 32
SPEED = 3


def _texture(seed=7, w=W + SPEED * T + 8, h=H):
    import numpy as np
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


def _clip(n=T, w=W, h=H):
    """Frame t shows the texture shifted left by SPEED*t, so content moves +SPEED px/frame in x...
    to move right, frame t starts at offset (n-1-t)*SPEED."""
    tex = _texture(w=w + SPEED * n + 8, h=h)
    return [tex[:, (n - 1 - t) * SPEED:(n - 1 - t) * SPEED + w].copy() for t in range(n)]


def _queries(t=0, n=16, w=W, h=H):
    import numpy as np
    rng = np.random.default_rng(3)
    xs = rng.uniform(20, w - 20 - SPEED * (32 - t), n)
    ys = rng.uniform(20, h - 20, n)
    return np.stack([np.full(n, t), xs, ys], 1).astype(np.float32)


def _truth(q, n_frames):
    import numpy as np
    t0 = q[:, 0]
    dt = np.arange(n_frames)[:, None] - t0[None, :]
    out = np.zeros((n_frames, len(q), 2), np.float32)
    out[..., 0] = q[None, :, 1] + SPEED * dt
    out[..., 1] = q[None, :, 2]
    return out


@needs_numpy
@needs_ml
class TrackAccuracy(unittest.TestCase):
    def test_translating_texture(self):
        import numpy as np
        from tools.vidkit import pointtrack
        frames = np.stack(_clip())
        q = _queries()
        tracks, visible = pointtrack.track(frames, q)
        self.assertEqual(tracks.shape, (T, 16, 2))
        self.assertEqual(visible.shape, (T, 16))
        err = np.linalg.norm(tracks - _truth(q, T), axis=2)
        self.assertGreaterEqual((err <= 1.5).mean(), 0.9)
        self.assertTrue(visible.all())

    def test_occlusion_hides_then_recovers(self):
        # The model flags a black occluder about 3 frames late, so the box stays 10 frames
        # (10-19); a 5-frame grey box measured 0-4 hidden frames and is not a reliable signal.
        import numpy as np
        from tools.vidkit import pointtrack
        frames = np.stack(_clip())
        frames[10:20, :, :140] = 0
        rng = np.random.default_rng(5)
        left = np.stack([np.zeros(8), rng.uniform(20, 80, 8), rng.uniform(20, H - 20, 8)], 1)
        right = np.stack([np.zeros(8), rng.uniform(160, 200, 8), rng.uniform(20, H - 20, 8)], 1)
        q = np.concatenate([left, right]).astype(np.float32)
        tracks, visible = pointtrack.track(frames, q)
        err = np.linalg.norm(tracks - _truth(q, T), axis=2)
        hidden = (~visible[10:20, :8]).sum(axis=0)
        print(f"\nocclusion: hidden frames per left point = {hidden.tolist()}; "
              f"max err frame 24 = {err[24].max():.2f}; right visible fraction 10-19 = "
              f"{visible[10:20, 8:].mean():.2f}")
        self.assertTrue((hidden >= 3).all())
        self.assertTrue(visible[24].all())
        self.assertTrue((err[24] <= 2.0).all())
        self.assertGreaterEqual(visible[10:20, 8:].mean(), 0.9)

    def test_query_mid_clip_tracks_both_ways(self):
        import numpy as np
        from tools.vidkit import pointtrack
        frames = np.stack(_clip())
        q = _queries(t=16)
        q[:, 1] = np.clip(q[:, 1], 60, W - 20 - SPEED * 16)
        tracks, visible = pointtrack.track(frames, q)
        truth = _truth(q, T)
        err = np.linalg.norm(tracks - truth, axis=2)
        print(f"\nmid-clip: before ok={(err[:16] <= 1.5).mean():.3f} after ok={(err[17:] <= 1.5).mean():.3f} "
              f"max err={err.max():.2f}")
        np.testing.assert_allclose(tracks[16], q[:, 1:], atol=1e-4)
        self.assertTrue(visible[16].all())
        self.assertGreaterEqual((err[:16] <= 1.5).mean(), 0.9)
        self.assertGreaterEqual((err[17:] <= 1.5).mean(), 0.9)

    def test_single_frame_single_point_odd_size(self):
        import numpy as np
        from tools.vidkit import pointtrack
        frames = np.random.default_rng(1).integers(0, 256, (1, 117, 203, 3), dtype=np.uint8)
        q = np.array([[0, 202, 116]], np.float32)
        tracks, visible = pointtrack.track(frames, q)
        self.assertEqual(tracks.shape, (1, 1, 2))
        self.assertEqual(visible.shape, (1, 1))
        np.testing.assert_allclose(tracks[0, 0], [202, 116], atol=1e-4)
        self.assertTrue(visible[0, 0])

    def test_odd_size_clip_maps_back_to_input_pixels(self):
        import numpy as np
        from tools.vidkit import pointtrack
        frames = np.stack(_clip(n=8, w=203, h=117))
        q = np.array([[0, 40.5, 30.25], [0, 90.0, 80.0]], np.float32)
        tracks, _ = pointtrack.track(frames, q)
        err = np.linalg.norm(tracks - _truth(q, 8), axis=2)
        print(f"\nodd size: max err={err.max():.2f}")
        self.assertLessEqual(err.max(), 3.0)


@needs_numpy
class TrackValidation(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.frames = np.zeros((4, 24, 32, 3), np.uint8)
        self.q = np.array([[0, 5, 5]], np.float32)

    def _fails(self, frames, q):
        from tools.vidkit import pointtrack
        with self.assertRaises(ValueError):
            pointtrack.track(frames, q)

    def test_no_frames(self):
        self._fails(self.frames[:0], self.q)

    def test_no_queries(self):
        self._fails(self.frames, self.q[:0])

    def test_x_outside(self):
        for x in (-1, 32, 100):
            self._fails(self.frames, [[0, x, 5]])

    def test_y_outside(self):
        for y in (-0.5, 24):
            self._fails(self.frames, [[0, 5, y]])

    def test_t_out_of_range(self):
        for t in (4, 9, -1):
            self._fails(self.frames, [[t, 5, 5]])

    def test_wrong_dims(self):
        import numpy as np
        self._fails(self.frames[0], self.q)
        self._fails(self.frames[..., :2], self.q)
        self._fails(self.frames.astype(np.float32), self.q)
        self._fails(self.frames, [5, 5, 0])
        self._fails(self.frames, [[0, 5]])

    def test_nan_query(self):
        self._fails(self.frames, [[0, float("nan"), 5]])


class ImportSafe(unittest.TestCase):
    def test_module_imports_without_ml_stack(self):
        from tools.vidkit import pointtrack
        self.assertTrue(callable(pointtrack.track))


if __name__ == "__main__":
    unittest.main()
