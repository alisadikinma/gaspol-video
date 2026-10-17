import importlib.util
import unittest

HAS_CV = bool(importlib.util.find_spec("numpy") and importlib.util.find_spec("cv2"))
needs_cv = unittest.skipUnless(HAS_CV, "numpy and cv2 not importable on this interpreter")

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


if __name__ == "__main__":
    unittest.main()
