import importlib.util
import unittest

HAS_CV = bool(importlib.util.find_spec("numpy") and importlib.util.find_spec("cv2"))
needs_cv = unittest.skipUnless(HAS_CV, "numpy and cv2 not importable on this interpreter")


def _ml_ready():
    if not (HAS_CV and importlib.util.find_spec("torch") and importlib.util.find_spec("tapnet")):
        return False
    from tools.vidkit import ml
    try:
        ml.weight("tapnextpp_ckpt.pt")
    except ml.MLMissing:
        return False
    return True


needs_ml = unittest.skipUnless(_ml_ready(), "torch, tapnet or TAPNext++ weights missing")

QUAD = [[200, 80], [450, 95], [440, 280], [190, 260]]
SKIN = (120, 160, 220)


def _frame(quad=QUAD, finger=True, w=640, h=360):
    import cv2
    import numpy as np
    img = np.full((h, w, 3), 128, np.uint8)
    cv2.fillPoly(img, [np.array(quad, np.int32)], (0, 255, 0), cv2.LINE_AA)
    if finger:
        cv2.rectangle(img, (300, 250), (330, 300), SKIN, -1)
    return img


def _max_err(got, want):
    import numpy as np
    return float(np.abs(np.asarray(got, float) - np.asarray(want, float)).max())


@needs_cv
class CornersGreenTest(unittest.TestCase):
    def test_corners_with_finger_over_bottom_edge(self):
        from tools.vidkit.screen import corners_green
        got = corners_green(_frame())
        self.assertIsNotNone(got)
        self.assertEqual(got.shape, (4, 2))
        print("finger err", _max_err(got, QUAD))
        self.assertLess(_max_err(got, QUAD), 2.0)

    def test_no_green_returns_none(self):
        from tools.vidkit.screen import corners_green
        import numpy as np
        self.assertIsNone(corners_green(np.full((360, 640, 3), 128, np.uint8)))

    def test_jpeg_compressed(self):
        import cv2
        from tools.vidkit.screen import corners_green
        ok, buf = cv2.imencode(".jpg", _frame(), [cv2.IMWRITE_JPEG_QUALITY, 70])
        self.assertTrue(ok)
        got = corners_green(cv2.imdecode(buf, cv2.IMREAD_COLOR))
        self.assertIsNotNone(got)
        err = _max_err(got, QUAD)
        print("jpeg err", err)
        self.assertLess(err, 2.0)

    def test_finger_over_bottom_right_corner(self):
        import cv2
        from tools.vidkit.screen import corners_green
        img = _frame(finger=False)
        cv2.rectangle(img, (425, 265), (455, 295), SKIN, -1)
        got = corners_green(img)
        self.assertIsNotNone(got)
        err = _max_err(got, QUAD)
        print("corner-finger err", err)
        self.assertLess(err, 3.0)

    def test_corner_outside_frame(self):
        from tools.vidkit.screen import corners_green
        quad = [[-20, 60], [450, 95], [440, 280], [190, 260]]
        got = corners_green(_frame(quad, finger=False))
        self.assertIsNotNone(got)
        err = _max_err(got, quad)
        print("border err", err)
        self.assertLess(err, 2.0)

    def test_two_blobs_largest_wins(self):
        import cv2
        import numpy as np
        from tools.vidkit.screen import corners_green
        img = _frame(finger=False)
        cv2.fillPoly(img, [np.array([[500, 20], [600, 20], [600, 70], [500, 70]], np.int32)],
                     (0, 255, 0), cv2.LINE_AA)
        got = corners_green(img)
        self.assertIsNotNone(got)
        err = _max_err(got, QUAD)
        print("two-blob err", err)
        self.assertLess(err, 2.0)

    def test_tiny_quad_returns_none(self):
        from tools.vidkit.screen import corners_green
        tiny = [[100, 100], [130, 100], [130, 160], [100, 160]]
        self.assertIsNone(corners_green(_frame(tiny, finger=False)))

    def test_clockwise_from_top_left(self):
        from tools.vidkit.screen import corners_green
        got = corners_green(_frame())
        self.assertEqual(int(got.sum(axis=1).argmin()), 0)
        self.assertLess(got[0][0], got[1][0])
        self.assertLess(got[1][1], got[2][1])


@needs_cv
class OneEuroTest(unittest.TestCase):
    # Contract defaults (1.0, 0.05, 1.0) cannot meet both: noise <= 1/3 needs a low min_cutoff,
    # lag < 2 px at 10 px/frame needs beta >= 0.1. Each behaviour is tested with its own params.

    def test_static_noise_reduced(self):
        import numpy as np
        from tools.vidkit.screen import OneEuro
        rng = np.random.default_rng(1)
        f = OneEuro(30, min_cutoff=0.2)
        xs = 100 + rng.uniform(-2, 2, (120, 2))
        ys = np.array([f(x) for x in xs])
        ratio = ys[10:].std(axis=0).max() / xs[10:].std(axis=0).min()
        print("std ratio out/in", ratio)
        self.assertLessEqual(ratio, 1 / 3)

    def test_constant_velocity_lag(self):
        import numpy as np
        from tools.vidkit.screen import OneEuro
        f = OneEuro(30, beta=0.2)
        errs = []
        for t in range(40):
            x = np.array([10.0 * t, 10.0 * t])
            errs.append(np.abs(f(x) - x).max())
        print("lag err frames5+", max(errs[5:]))
        self.assertLess(max(errs[5:]), 2.0)

    def test_first_call_identity_and_shape(self):
        import numpy as np
        from tools.vidkit.screen import OneEuro
        f = OneEuro(30)
        x = np.arange(8, dtype=float).reshape(4, 2)
        np.testing.assert_array_equal(f(x), x)
        self.assertEqual(f(x + 1).shape, (4, 2))

    def test_bad_fps(self):
        from tools.vidkit.screen import OneEuro
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                OneEuro(bad)


WORLD_SCREEN = [[170, 130], [340, 140], [330, 250], [160, 240]]
WORLD_BEZEL = [[145, 105], [365, 115], [355, 275], [135, 265]]


def _world():
    """Textured background, a darker textured bezel quad, a differently textured screen quad."""
    import cv2
    import numpy as np
    rng = np.random.default_rng(11)
    w = rng.integers(0, 256, (560, 760, 3), dtype=np.uint8)
    w = cv2.GaussianBlur(w, (0, 0), 0.8)
    bez = (rng.integers(0, 120, (560, 760, 3), dtype=np.uint8))
    scr = rng.integers(60, 256, (560, 760, 3), dtype=np.uint8)
    for quad, tex in ((WORLD_BEZEL, bez), (WORLD_SCREEN, scr)):
        m = np.zeros(w.shape[:2], np.uint8)
        cv2.fillPoly(m, [np.array(quad, np.int32)], 255)
        w[m > 0] = tex[m > 0]
    return cv2.GaussianBlur(w, (0, 0), 0.6)


def _synthetic(n=40, offset=(80.0, 60.0), size=(480, 320), still=0):
    """Frames (RGB uint8) and true screen corners per frame; pan 2 px/frame, 3 deg roll, 1.0->1.04.
    The first ``still`` frames hold the pose of frame 0."""
    import cv2
    import numpy as np
    world = _world()
    cx, cy = 250.0, 190.0
    frames, truth = [], []
    for t in range(n):
        k = max(0, t - still) / max(1, n - 1 - still)
        ang = np.deg2rad(3.0 * k)
        sc = 1.0 + 0.04 * k
        c, s = np.cos(ang) * sc, np.sin(ang) * sc
        rot = np.array([[c, -s, cx - c * cx + s * cy], [s, c, cy - s * cx - c * cy], [0, 0, 1]])
        tr = np.array([[1, 0, -offset[0] + 2.0 * max(0, t - still)], [0, 1, -offset[1]], [0, 0, 1]])
        m = tr @ rot
        frames.append(cv2.warpPerspective(world, m, size, flags=cv2.INTER_LINEAR,
                                          borderMode=cv2.BORDER_REFLECT))
        q = np.array(WORLD_SCREEN, np.float64).reshape(-1, 1, 2)
        truth.append(cv2.perspectiveTransform(q, m).reshape(4, 2))
    return np.stack(frames), np.stack(truth)


@needs_ml
class CornersTrackTest(unittest.TestCase):
    def test_tracks_known_homography_sequence(self):
        import numpy as np
        from tools.vidkit.screen import corners_track
        frames, truth = _synthetic()
        got, inl = corners_track(frames, truth[0])
        self.assertEqual(got.shape, (40, 4, 2))
        self.assertEqual(inl.shape, (40,))
        errs = np.linalg.norm(got - truth, axis=2).max(axis=1)
        print("track corner err max %.2f mean %.2f min inlier %.2f" % (errs.max(), errs.mean(), inl.min()))
        self.assertLess(errs.max(), 3.0)

    def test_jitter_on_static_segment(self):
        import numpy as np
        from tools.vidkit.screen import corners_track
        frames, truth = _synthetic(n=40, still=20)
        got, _ = corners_track(frames, truth[0])
        seg = got[:20]
        step = np.linalg.norm(np.diff(seg, axis=0), axis=2).max()
        err = np.linalg.norm(got[:20] - truth[:20], axis=2).max()
        print("static 20 frames: max frame-to-frame step %.3f px, max err %.3f px" % (step, err))
        self.assertLess(step, 0.5)

    def test_corner_outside_frame(self):
        import numpy as np
        from tools.vidkit.screen import corners_track
        frames, truth = _synthetic(offset=(185.0, 60.0))
        self.assertLess(truth[0][0][0], 0)
        got, _ = corners_track(frames, truth[0])
        errs = np.linalg.norm(got - truth, axis=2).max(axis=1)
        print("partly outside err max %.2f" % errs.max())
        self.assertLess(errs.max(), 4.0)


@needs_cv
class CornersTrackInputTest(unittest.TestCase):
    def _frames(self):
        import numpy as np
        return np.zeros((3, 100, 100, 3), np.uint8)

    def test_counter_clockwise_refused(self):
        from tools.vidkit.screen import corners_track
        with self.assertRaises(ValueError):
            corners_track(self._frames(), [[20, 20], [20, 80], [80, 80], [80, 20]])

    def test_degenerate_refused(self):
        from tools.vidkit.screen import corners_track
        with self.assertRaises(ValueError):
            corners_track(self._frames(), [[20, 20], [28, 20], [28, 28], [20, 28]])


@needs_cv
class CheckTrackTest(unittest.TestCase):
    FPS = 30.0
    DIAG = 300.0

    def _ok(self, t=60):
        import numpy as np
        base = np.array([[100, 100], [300, 100], [300, 250], [100, 250]], float)
        corners = np.stack([base + [0.5 * i, 0.0] for i in range(t)])
        return corners, np.ones(t), np.ones((t, 40), bool)

    def test_clean_passes(self):
        from tools.vidkit.screen import check_track
        c, i, v = self._ok()
        check_track(c, i, v, self.FPS, self.DIAG)

    def test_hand_40pct_for_0p3s_passes(self):
        from tools.vidkit.screen import check_track
        c, i, v = self._ok()
        v[10:19, :16] = False  # 9 frames = 0.3 s, 40% of points
        check_track(c, i, v, self.FPS, self.DIAG)

    def test_hand_40pct_for_0p6s_refuses(self):
        from tools.vidkit.screen import Refused, check_track
        c, i, v = self._ok()
        v[10:28, :16] = False  # 18 frames = 0.6 s
        with self.assertRaises(Refused) as cm:
            check_track(c, i, v, self.FPS, self.DIAG)
        self.assertEqual(str(cm.exception), "track lost on frames 10-27 (40% points hidden)")

    def test_exactly_half_second_refuses(self):
        from tools.vidkit.screen import Refused, check_track
        c, i, v = self._ok()
        v[5:20, :20] = False  # 15 frames = 0.5 s, 50%
        with self.assertRaises(Refused) as cm:
            check_track(c, i, v, self.FPS, self.DIAG)
        self.assertIn("track lost on frames 5-19", str(cm.exception))

    def test_30pct_exactly_is_not_over(self):
        from tools.vidkit.screen import check_track
        c, i, v = self._ok()
        v[5:40, :12] = False  # exactly 30% hidden: not > 30%
        check_track(c, i, v, self.FPS, self.DIAG)

    def test_corner_jump_refuses(self):
        from tools.vidkit.screen import Refused, check_track
        c, i, v = self._ok()
        c[30:, 2] += [30.0, 0.0]  # 30 px > 8% of 300 = 24 px
        with self.assertRaises(Refused) as cm:
            check_track(c, i, v, self.FPS, self.DIAG)
        self.assertEqual(str(cm.exception), "corner jump 30.5 px at frame 30")

    def test_corner_jump_just_under_passes(self):
        from tools.vidkit.screen import check_track
        c, i, v = self._ok()
        c[30:, 2] += [23.0, 0.0]
        check_track(c, i, v, self.FPS, self.DIAG)

    def test_inlier_049_refuses(self):
        from tools.vidkit.screen import Refused, check_track
        c, i, v = self._ok()
        i[12] = 0.49
        with self.assertRaises(Refused) as cm:
            check_track(c, i, v, self.FPS, self.DIAG)
        self.assertEqual(str(cm.exception), "homography unstable at frame 12 (inliers 0.49)")

    def test_inlier_050_passes(self):
        from tools.vidkit.screen import check_track
        c, i, v = self._ok()
        i[12] = 0.5
        check_track(c, i, v, self.FPS, self.DIAG)


if __name__ == "__main__":
    unittest.main()
