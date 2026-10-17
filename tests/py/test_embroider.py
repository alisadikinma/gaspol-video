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


def _field(x, y):
    import numpy as np
    return 6.0 * np.sin(y / 40.0), 4.0 * np.cos(x / 50.0)


def _grid_points(n=7, x0=50, x1=350, y0=40, y1=260):
    import numpy as np
    gx, gy = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
    return np.stack([gx.ravel(), gy.ravel()], 1).astype(np.float32)


def _checker_layer(w=400, h=300, cell=25, hull=(50, 40, 350, 260)):
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    check = (((xx // cell) + (yy // cell)) % 2).astype(np.uint8) * 200 + 30
    layer = np.zeros((h, w, 4), np.uint8)
    layer[..., :3] = check[..., None]
    inside = (xx >= hull[0]) & (xx <= hull[2]) & (yy >= hull[1]) & (yy <= hull[3])
    layer[..., 3] = inside * 255
    return layer


@needs_cv
class GridWarpTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def _warp(self, layer, src, dst, visible=None):
        import numpy as np
        if visible is None:
            visible = np.ones(len(src), bool)
        return self.e.grid_warp(layer, src, dst, visible, (layer.shape[1], layer.shape[0]))

    def test_matches_analytic_field_per_cell(self):
        import cv2
        import numpy as np
        layer = _checker_layer()
        src = _grid_points()
        dx, dy = _field(src[:, 0], src[:, 1])
        dst = src + np.stack([dx, dy], 1).astype(np.float32)
        out = self._warp(layer, src, dst)
        h, w = layer.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        sx, sy = xx.copy(), yy.copy()
        for _ in range(2):
            fx, fy = _field(sx, sy)
            sx, sy = xx - fx, yy - fy
        truth = cv2.remap(layer, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        errs = []
        cell = 25
        for cy in range(2, 9):
            for cx in range(2, 13):
                x0, y0 = cx * cell, cy * cell
                if (cx + cy) % 2:
                    continue
                cents = []
                for img in (out, truth):
                    win = img[y0 - 8:y0 + cell + 8, x0 - 8:x0 + cell + 8]
                    a = win[..., 3].astype(np.float32) * (win[..., 0] > 128)
                    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
                    tot = a.sum()
                    if tot == 0:
                        break
                    cents.append(((a * xs).sum() / tot, (a * ys).sum() / tot))
                if len(cents) == 2:
                    errs.append(np.hypot(cents[0][0] - cents[1][0], cents[0][1] - cents[1][1]))
        self.assertGreater(len(errs), 20)
        print("centroid error mean=%.3f max=%.3f" % (np.mean(errs), np.max(errs)))
        self.assertLessEqual(float(np.mean(errs)), 1.5)

    def test_identity(self):
        import numpy as np
        layer = _checker_layer()
        src = _grid_points()
        out = self._warp(layer, src, src.copy())
        inner = (slice(46, 254), slice(56, 344))
        diff = np.abs(out.astype(int) - layer.astype(int))[inner]
        self.assertLessEqual(int(diff.max()), 1)

    def test_invisible_points_ignored(self):
        import numpy as np
        layer = _checker_layer()
        src = _grid_points()
        dx, dy = _field(src[:, 0], src[:, 1])
        dst = src + np.stack([dx, dy], 1).astype(np.float32)
        visible = np.ones(len(src), bool)
        visible[10] = False
        a = self._warp(layer, src, dst, visible)
        dst2 = dst.copy()
        dst2[10] += (300, -200)
        b = self._warp(layer, src, dst2, visible)
        self.assertTrue(np.array_equal(a, b))

    def test_too_few_or_collinear_refused(self):
        import numpy as np
        from tools.vidkit.screen import Refused
        layer = _checker_layer()
        src = _grid_points()
        visible = np.zeros(len(src), bool)
        visible[[0, 1, 2]] = True
        with self.assertRaises(Refused) as ctx:
            self._warp(layer, src, src.copy(), visible)
        self.assertIn("track lost: 3 visible points", str(ctx.exception))
        line = np.array([[50, 50], [100, 50], [150, 50], [200, 50], [250, 50]], np.float32)
        with self.assertRaises(Refused):
            self._warp(layer, line, line.copy())

    def test_multichannel_float_layer(self):
        import numpy as np
        h, w = 300, 400
        rng = np.random.default_rng(1)
        layer = np.zeros((h, w, 8), np.float32)
        layer[50:250, 60:340] = rng.random((200, 280, 8)).astype(np.float32) * 0 + np.linspace(0, 1, 8, dtype=np.float32)
        src = _grid_points()
        out = self._warp(layer, src, src.copy())
        self.assertEqual(out.shape, (h, w, 8))
        self.assertEqual(out.dtype, np.float32)
        self.assertLess(float(np.abs(out[60:240, 70:330] - layer[60:240, 70:330]).max()), 1e-3)


def _shade_inputs(h=100, w=300):
    import numpy as np
    ramp = np.linspace(40, 220, w, dtype=np.float32)
    frame = np.repeat(np.repeat(ramp[None, :, None], h, 0), 3, 2).astype(np.uint8)
    alpha = np.zeros((h, w), np.float32)
    alpha[20:80, 60:240] = 1.0
    albedo = np.full((h, w, 3), 0.5, np.float32)
    return frame, albedo, alpha


@needs_cv
class ShadeTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def test_follows_cloth_luminance(self):
        import numpy as np
        frame, albedo, alpha = _shade_inputs()
        h, w = alpha.shape
        normal = np.zeros((h, w, 3), np.float32)
        normal[..., 2] = 1
        out = self.e.shade(frame, albedo, normal, np.full((h, w), 0.5, np.float32), alpha)
        self.assertEqual(out.dtype, np.uint8)
        row_out = out[50, 75:225].mean(axis=1)
        row_in = frame[50, 75:225].mean(axis=1)
        corr = float(np.corrcoef(row_out, row_in)[0, 1])
        print("shade correlation=%.4f" % corr)
        self.assertGreaterEqual(corr, 0.8)

    def test_ridges_brighter_than_valleys(self):
        import numpy as np
        frame, albedo, alpha = _shade_inputs()
        frame[:] = 128
        h, w = alpha.shape
        xs = np.arange(w, dtype=np.float32)
        height = np.tile((0.5 + 0.5 * np.sin(xs / 3.0))[None, :], (h, 1)).astype(np.float32)
        slope = np.tile((0.5 * np.cos(xs / 3.0) / 3.0)[None, :], (h, 1))
        normal = np.dstack([-slope * 6, np.zeros_like(slope), np.ones_like(slope)])
        normal /= np.linalg.norm(normal, axis=2, keepdims=True)
        out = self.e.shade(frame, albedo, normal.astype(np.float32), height, alpha)
        lum = out.mean(axis=2)
        core = alpha > 0
        core[:, :80] = False
        core[:, 220:] = False
        top = lum[core & (height > 0.9)].mean()
        valley = lum[core & (height < 0.1)].mean()
        print("ridge/valley ratio=%.3f" % (top / valley))
        self.assertGreater(top, valley)

    def test_outside_alpha_equals_frame(self):
        import numpy as np
        frame, albedo, alpha = _shade_inputs()
        h, w = alpha.shape
        normal = np.zeros((h, w, 3), np.float32)
        normal[..., 2] = 1
        out = self.e.shade(frame, albedo, normal, np.full((h, w), 0.5, np.float32), alpha)
        self.assertTrue(np.array_equal(out[alpha == 0], frame[alpha == 0]))


if __name__ == "__main__":
    unittest.main()
