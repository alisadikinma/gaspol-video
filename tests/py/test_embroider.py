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


def _text_logo(w=140, h=40):
    """Small logo like the REA design at output size: teal underline, black strokes, 3 px wide."""
    import numpy as np
    img = np.zeros((h, w, 4), np.uint8)
    img[30:34, 10:130] = (166, 166, 0, 255)                       # teal underline, BGR
    for x in range(12, 128, 12):
        img[6:26, x:x + 3] = (0, 0, 0, 255)                       # black stems
        img[6:9, x:x + 8] = (0, 0, 0, 255)
    return img


@needs_cv
class MinimumStrokeTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def test_one_pixel_stroke_grows(self):
        import numpy as np
        thin = _bar(w=200, h=60, rows=(30, 31), cols=(10, 190))
        before = self.e.stroke_half_width(thin)
        grown = self.e.ensure_min_stroke(thin)
        after = self.e.stroke_half_width(grown)
        print("1 px stroke half-width %.2f -> %.2f" % (before, after))
        self.assertLess(before, self.e.MIN_STROKE_HALF_PX)
        self.assertGreaterEqual(after, self.e.MIN_STROKE_HALF_PX)
        self.assertTrue((grown[30, 20:180, :3] == thin[30, 20:180, :3]).all())
        self.assertTrue((grown[29, 20:180, 3] > 0).all() and (grown[31, 20:180, 3] > 0).all())

    def test_thick_logo_unchanged(self):
        import numpy as np
        thick = _bar()
        self.assertTrue(np.array_equal(self.e.ensure_min_stroke(thick), thick))

    def test_grown_pixels_take_the_nearest_colour(self):
        import numpy as np
        thin = _bar(w=200, h=60, rows=(30, 31), cols=(10, 190), color=(40, 90, 200))
        grown = self.e.ensure_min_stroke(thin)
        sel = grown[..., 3] > 0
        self.assertTrue((grown[sel][:, :3] == np.array([40, 90, 200])).all())


@needs_cv
class ReliefTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def test_relief_has_stitch_structure_at_output_size(self):
        import numpy as np
        logo = _text_logo()
        albedo, alpha, relief, sheen = self.e.relief_maps(self.e.ensure_min_stroke(logo))
        core = cv2_erode(alpha > 0.99)
        std = float(relief[core].std())
        print("relief std in stroke cores = %.4f (mean %.3f), sheen max %.3f" % (std, relief[core].mean(), sheen.max()))
        self.assertEqual(relief.shape, logo.shape[:2])
        self.assertGreaterEqual(std, 0.05)
        self.assertGreater(sheen.max(), 0.02)

    def test_relief_deterministic(self):
        import numpy as np
        a = self.e.relief_maps(_text_logo())
        b = self.e.relief_maps(_text_logo())
        for x, y in zip(a, b):
            self.assertTrue(np.array_equal(x, y))


def cv2_erode(mask):
    import cv2
    import numpy as np
    return cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def _lab_stats(bgr_float, sel):
    import cv2
    import numpy as np
    lab = cv2.cvtColor(bgr_float.astype(np.float32), cv2.COLOR_BGR2Lab)
    a, b = lab[..., 1][sel].mean(), lab[..., 2][sel].mean()
    return float(np.hypot(a, b)), float(np.degrees(np.arctan2(b, a)))


@needs_cv
class ThreadColourTest(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from tools.vidkit import embroider
        self.e = embroider
        self.logo = _text_logo()
        size = (200, 100)
        layer = embroider._canvas_layer(embroider.ensure_min_stroke(self.logo), 30, 30, size, np)
        frame = np.full((100, 200, 3), 128, np.uint8)
        self.layer = layer
        self.out = embroider._shade_layer(frame, layer, layer[..., 3])

    def test_teal_line_stays_teal_and_black_stays_black(self):
        import numpy as np
        ys, xs = 30 + 31, slice(30 + 30, 30 + 110)
        teal_out = self.out[ys, xs].astype(np.float32) / 255
        teal_logo = np.array([[[166, 166, 0]]], np.float32) / 255
        c_out, h_out = _lab_stats(teal_out[None], np.ones((1, teal_out.shape[0]), bool))
        c_logo, h_logo = _lab_stats(teal_logo, np.ones((1, 1), bool))
        print("teal chroma ratio %.3f, hue %.1f vs %.1f" % (c_out / c_logo, h_out, h_logo))
        self.assertGreaterEqual(c_out / c_logo, 0.8)
        self.assertLessEqual(abs(h_out - h_logo) / abs(h_logo), 0.06)
        stem = self.out[30 + 12:30 + 22, 30 + 24:30 + 27].astype(np.float32)
        print("black stem mean level %.1f" % stem.mean())
        self.assertLess(float(stem.mean()), 45.0)

    def test_design_chroma_within_six_percent_under_neutral_light(self):
        import numpy as np
        sel = self.layer[..., 3] > 0.99
        sel = cv2_erode(sel)
        logo_full = np.zeros((100, 200, 3), np.float32)
        logo_full[30:70, 30:170] = self.logo[..., :3].astype(np.float32) / 255
        teal = np.zeros(sel.shape, bool)
        teal[61:64, 60:140] = True
        teal &= sel
        c_out, _ = _lab_stats(self.out.astype(np.float32) / 255, teal)
        c_logo, _ = _lab_stats(logo_full, teal)
        print("design chroma ratio %.3f" % (c_out / c_logo))
        self.assertLessEqual(abs(c_out / c_logo - 1.0), 0.06)


@needs_cv
class EdgeFuzzTest(unittest.TestCase):
    def setUp(self):
        from tools.vidkit import embroider
        self.e = embroider

    def test_deterministic_and_interior_untouched(self):
        import cv2
        import numpy as np
        alpha = (_bar(w=100, h=60, rows=(15, 45), cols=(10, 90))[..., 3] / 255.0).astype(np.float32)
        a = self.e.edge_fuzz(alpha)
        b = self.e.edge_fuzz(alpha)
        self.assertTrue(np.array_equal(a, b))
        interior = cv2.erode((alpha > 0).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        self.assertTrue(np.array_equal(a[interior], alpha[interior]))
        self.assertTrue((a[alpha == 0] == 0).all())
        edge = (alpha > 0) & ~interior
        self.assertGreater(float(np.abs(a[edge] - alpha[edge]).max()), 0.05)
        self.assertLessEqual(float(np.abs(a - alpha).max()), self.e.EDGE_FUZZ + 1e-6)
        self.assertTrue(((a >= 0) & (a <= 1)).all())


def _ml_ready():
    if not (HAS_CV and importlib.util.find_spec("torch") and importlib.util.find_spec("tapnet")):
        return False
    from tools.vidkit import ml
    try:
        ml.weight("tapnextpp_ckpt.pt")
        ml.weight("sam2.1_hiera_small.pt")
    except ml.MLMissing:
        return False
    return True


needs_ml = unittest.skipUnless(_ml_ready(), "torch, sam2, tapnet or the ML weights missing")

SIZE = 320
FRAMES = 24
HAND_FRAMES = range(8, 17)
AT = (160, 160)


def _synthetic_clip():
    """Textured grey shirt on a green background, deforming by a known smooth field, plus a skin
    disc that sweeps left to right across the shirt. Returns frames [T,H,W,3] BGR, shirt masks and
    hand masks [T,H,W] bool (the known ground truth)."""
    import cv2
    import numpy as np
    rng = np.random.default_rng(24)
    tex = rng.normal(0, 1, (SIZE, SIZE)).astype(np.float32)
    tex = cv2.GaussianBlur(tex, (0, 0), 1.2)
    tex = tex / tex.std()
    base = np.empty((SIZE, SIZE, 3), np.uint8)
    base[:] = (30, 100, 60)
    shirt0 = np.zeros((SIZE, SIZE), np.uint8)
    cv2.rectangle(shirt0, (50, 40), (270, 290), 255, -1)
    grey = np.clip(128 + 28 * tex, 0, 255).astype(np.uint8)
    base[shirt0 > 0] = np.stack([grey] * 3, axis=-1)[shirt0 > 0]
    ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    frames, shirts, hands = [], [], []
    for t in range(FRAMES):
        dx = 4 * np.sin(2 * np.pi * ys / 160 + 0.2 * t)
        dy = 3 * np.cos(2 * np.pi * xs / 200 + 0.2 * t)
        mx, my = xs + dx, ys + dy
        frame = cv2.remap(base, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        shirt = cv2.remap(shirt0, mx, my, cv2.INTER_NEAREST) > 0
        hand = np.zeros((SIZE, SIZE), np.uint8)
        cx = int(25 + 270 * t / (FRAMES - 1))
        cv2.circle(hand, (cx, 165), 22, 255, -1)
        frame[hand > 0] = (120, 160, 220)
        frames.append(frame)
        shirts.append(shirt)
        hands.append(hand > 0)
    return np.stack(frames), np.stack(shirts), np.stack(hands)


def _red_bar(w=60, h=30):
    import numpy as np
    img = np.zeros((h, w, 4), np.uint8)
    img[..., 2] = 255
    img[..., 3] = 255
    return img


def _write_clip(frames, path, audio):
    import subprocess
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{SIZE}x{SIZE}",
           "-r", "24", "-i", "-"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "10", path]
    subprocess.run(cmd, input=frames.tobytes(), check=True)


@needs_ml
class EmbroiderRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.vidkit import embroider
        cls.e = embroider
        cls.frames, cls.shirt, cls.hand = _synthetic_clip()
        cls.out, cls.info = embroider._render(cls.frames, _red_bar(), AT, 60, 0.0, [[25, 165]], 24.0)

    def test_info(self):
        self.assertEqual(self.info["frames"], FRAMES)
        self.assertGreater(self.info["shirt_area_ratio"], 1.5)
        print("lost_frames=%d ratio=%.2f" % (self.info["lost_frames"], self.info["shirt_area_ratio"]))
        self.assertLessEqual(self.info["lost_frames"], len(HAND_FRAMES))

    def test_off_shirt_unchanged(self):
        import cv2
        import numpy as np
        worst = 0
        for t in range(FRAMES):
            far = ~(cv2.dilate(self.shirt[t].astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
            worst = max(worst, int((self.out[t][far] != self.frames[t][far]).any(axis=-1).sum()))
        print("off-shirt pixels changed (max over frames) = %d" % worst)
        self.assertEqual(worst, 0)

    def test_under_hand_unchanged(self):
        import cv2
        import numpy as np
        worst = 0
        for t in HAND_FRAMES:
            core = cv2.erode(self.hand[t].astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            worst = max(worst, int((self.out[t][core] != self.frames[t][core]).any(axis=-1).sum()))
        print("under-hand pixels changed (max over frames) = %d" % worst)
        self.assertEqual(worst, 0)

    def test_design_present_every_frame(self):
        import cv2
        import numpy as np
        counts = []
        for t in range(FRAMES):
            o = self.out[t].astype(np.int32)
            red = (o[..., 2] > o[..., 1] + 60) & (o[..., 2] > o[..., 0] + 60)
            red &= ~(cv2.dilate(self.hand[t].astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
            counts.append(int(red.sum()))
        print("design-red pixels per frame: min %d max %d" % (min(counts), max(counts)))
        self.assertGreater(min(counts), 150)

    def test_design_follows_the_cloth(self):
        import numpy as np
        def centroid(t):
            o = self.out[t].astype(np.int32)
            red = (o[..., 2] > o[..., 1] + 60) & (o[..., 2] > o[..., 0] + 60) & ~self.hand[t]
            ys, xs = np.nonzero(red)
            return np.array([xs.mean(), ys.mean()])
        drift = np.linalg.norm(centroid(0) - centroid(5))
        self.assertLess(drift, 12.0)


FLAT_FRAMES = 6


def _flat_clip():
    """Static clip: uniform grey shirt (no texture, no hand) on a green background."""
    import numpy as np
    frame = np.empty((SIZE, SIZE, 3), np.uint8)
    frame[:] = (30, 100, 60)
    frame[40:291, 50:271] = 128
    return np.repeat(frame[None], FLAT_FRAMES, axis=0)


@needs_ml
class EmbroideryRaisedShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.vidkit import embroider
        cls.frames = _flat_clip()
        cls.out, _ = embroider._render(cls.frames, _red_bar(), AT, 60, 0.0, None, 24.0)

    def test_shadow_falls_away_from_the_light(self):
        import numpy as np
        t = FLAT_FRAMES - 1
        delta = self.out[t].astype(np.float32).mean(axis=2) - self.frames[t].astype(np.float32).mean(axis=2)
        strong = delta < -30                              # the red bar: much darker than the grey cloth
        ys, xs = np.nonzero(strong)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        mid_y, mid_x = slice((y0 + y1) // 2 - 6, (y0 + y1) // 2 + 7), slice((x0 + x1) // 2 - 15, (x0 + x1) // 2 + 16)
        shadow_side = delta[mid_y, x1 + 1:x1 + 4].mean()  # right of the bar: away from the light (upper left)
        light_side = delta[mid_y, x0 - 3:x0].mean()   # left of the bar: toward the light
        below = delta[y1 + 1:y1 + 4, mid_x].mean()
        above = delta[y0 - 3:y0, mid_x].mean()
        print("shadow delta: right %.2f left %.2f below %.2f above %.2f" % (shadow_side, light_side, below, above))
        self.assertGreaterEqual(light_side - shadow_side, 4.0)
        self.assertGreaterEqual(above - below, 4.0)

    def test_far_pixels_unchanged(self):
        import numpy as np
        for t in range(FLAT_FRAMES):
            changed = (self.out[t] != self.frames[t]).any(axis=2)
            ys, xs = np.nonzero(changed)
            self.assertGreater(len(ys), 0)
            self.assertGreaterEqual(xs.min(), 130 - 8)
            self.assertLessEqual(xs.max(), 189 + 8)
            self.assertGreaterEqual(ys.min(), 145 - 8)
            self.assertLessEqual(ys.max(), 174 + 8)


@needs_ml
class EmbroiderRefusalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.vidkit import embroider
        cls.e = embroider
        cls.frames, _, _ = _synthetic_clip()

    def test_at_off_the_shirt(self):
        import numpy as np
        from unittest import mock
        from tools.vidkit.screen import Refused
        empty = np.zeros((FRAMES, SIZE, SIZE), bool)
        with mock.patch("tools.vidkit.segment.masks", return_value=empty):
            with self.assertRaisesRegex(Refused, "--at is not on the shirt"):
                self.e._render(self.frames, _red_bar(), AT, 60, 0.0, None, 24.0)

    def test_design_larger_than_shirt(self):
        from tools.vidkit.screen import Refused
        with self.assertRaisesRegex(Refused, r"shirt area too small for design \(\d+\.\d+\)"):
            self.e._render(self.frames, _red_bar(), AT, 300, 0.0, None, 24.0)

    def test_logo_without_alpha(self):
        import numpy as np
        with self.assertRaises(ValueError):
            self.e._render(self.frames, np.zeros((30, 60, 3), np.uint8), AT, 60, 0.0, None, 24.0)

    def test_track_lost(self):
        import numpy as np
        from unittest import mock
        from tools.vidkit.screen import Refused
        vis = np.zeros((FRAMES, 49), bool)
        tracks = np.zeros((FRAMES, 49, 2), np.float32)
        with mock.patch("tools.vidkit.pointtrack.track", return_value=(tracks, vis)):
            with self.assertRaisesRegex(Refused, r"track lost on frames 0-23 \(100% points hidden\)"):
                self.e._render(self.frames, _red_bar(), AT, 60, 0.0, None, 24.0)


@needs_ml
class EmbroiderE2ETest(unittest.TestCase):
    def _run(self, audio):
        import os
        import tempfile
        from tools.vidkit import embroider, ff
        frames, _, _ = _synthetic_clip()
        with tempfile.TemporaryDirectory() as d:
            clip, logo, out = (os.path.join(d, n) for n in ("in.mp4", "logo.png", "out.mp4"))
            import cv2
            cv2.imwrite(logo, _red_bar())
            _write_clip(frames, clip, audio)
            res = embroider.embroider(clip, logo, out, AT, 60, hand_points=[[25, 165]], qa_dir=os.path.join(d, "qa"))
            src, dst = ff.probe(clip), ff.probe(out)
            self.assertEqual(res["frames"], FRAMES)
            self.assertLessEqual(abs(src["video"]["duration"] - dst["video"]["duration"]), 1 / 24 + 1e-3)
            self.assertEqual(bool(src.get("audio")), bool(dst.get("audio")))
            self.assertTrue(os.path.isfile(os.path.join(d, "qa", "qa-embroider.jpg")))

    def test_with_audio(self):
        self._run(True)

    def test_without_audio(self):
        self._run(False)


if __name__ == "__main__":
    unittest.main()
