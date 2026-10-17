import importlib.util
import unittest

HAS_CV = bool(importlib.util.find_spec("numpy") and importlib.util.find_spec("cv2"))
needs_cv = unittest.skipUnless(HAS_CV, "numpy and cv2 not importable on this interpreter")


def _bar(w=200, h=80, rows=(20, 60), cols=(10, 190), color=(40, 90, 200)):
    import numpy as np
    img = np.zeros((h, w, 4), np.uint8)
    img[rows[0]:rows[1], cols[0]:cols[1], :3] = color
    img[rows[0]:rows[1], cols[0]:cols[1], 3] = 255
    return img


def _period(row):
    import numpy as np
    x = row - row.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    spec[0] = 0
    k = int(np.argmax(spec))
    return len(x) / k


@needs_cv
class ThreadMapsTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def test_bar_geometry_and_periods(self):
        import numpy as np
        bar = _bar()
        for stitch in (3.0, 5.0):
            height, normal, albedo = self.e.thread_maps(bar, stitch_px=stitch, angle_deg=90)
            self.assertEqual(height.dtype, np.float32)
            self.assertEqual(height.shape, (80, 200))
            self.assertEqual(normal.shape, (80, 200, 3))
            self.assertEqual(albedo.shape, (80, 200, 3))
            self.assertTrue(np.all(height[bar[..., 3] == 0] == 0))
            self.assertTrue(np.all(normal[..., 2] > 0))
            centre_err = np.abs(np.argmax(height[:, 30:170], axis=0) - 39.5).max()
            self.assertLessEqual(centre_err, 2.0)
            period = _period(height[40, 20:180])
            self.assertAlmostEqual(period, stitch, delta=0.5, msg=f"stitch {stitch}: {period}")

    def test_auto_angle_ridges_along_bar(self):
        height, _, _ = self.e.thread_maps(_bar(), stitch_px=3.0)
        self.assertAlmostEqual(_period(height[40, 20:180]), 3.0, delta=0.5)

    def test_no_opaque_pixels(self):
        import numpy as np
        with self.assertRaisesRegex(ValueError, "logo has no opaque pixels"):
            self.e.thread_maps(np.zeros((10, 10, 4), np.uint8))

    def test_not_rgba(self):
        import numpy as np
        with self.assertRaises(ValueError):
            self.e.thread_maps(np.zeros((10, 10, 3), np.uint8))

    def test_thin_stroke_rises(self):
        bar = _bar(rows=(30, 32))
        height, _, _ = self.e.thread_maps(bar, angle_deg=90)
        self.assertTrue((height[30:32, 10:190] > 0).all())

    def test_deterministic(self):
        import numpy as np
        a = self.e.thread_maps(_bar())
        b = self.e.thread_maps(_bar())
        for x, y in zip(a, b):
            self.assertTrue(np.array_equal(x, y))

    def test_albedo_within_six_percent(self):
        import numpy as np
        bar = _bar()
        _, _, albedo = self.e.thread_maps(bar, angle_deg=90)
        base = np.array([40, 90, 200], np.float32) / 255
        px = albedo[20:60, 10:190]
        self.assertTrue((px >= 0).all() and (px <= 1).all())
        self.assertTrue((np.abs(px - base) <= 0.06 * base + 1e-6).all())
        self.assertGreater(px[..., 2].max() - px[..., 2].min(), 0.01)

    def test_one_pixel_logo(self):
        import numpy as np
        px = np.array([[[10, 20, 30, 255]]], np.uint8)
        height, normal, albedo = self.e.thread_maps(px)
        self.assertEqual(height.shape, (1, 1))
        self.assertGreater(height[0, 0], 0)
        self.assertGreater(normal[0, 0, 2], 0)

    def test_wide_logo_downscaled(self):
        bar = _bar(w=2500, h=100, rows=(20, 80), cols=(100, 2400))
        height, normal, albedo = self.e.thread_maps(bar)
        self.assertEqual(height.shape[1], 2000)
        self.assertEqual(height.shape[0], 80)
        self.assertEqual(normal.shape[:2], height.shape)
        self.assertEqual(albedo.shape[:2], height.shape)


if __name__ == "__main__":
    unittest.main()
