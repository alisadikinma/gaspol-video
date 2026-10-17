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


CQUAD = [[200.0, 80.0], [450.0, 95.0], [440.0, 280.0], [190.0, 260.0]]


def _scene(w=640, h=360):
    """Textured grey frame with a green quad."""
    import cv2
    import numpy as np
    rng = np.random.default_rng(5)
    img = cv2.GaussianBlur(rng.integers(90, 170, (h, w, 3), dtype=np.uint8), (0, 0), 1.2)
    cv2.fillPoly(img, [np.array(CQUAD, np.int32)], (0, 255, 0), cv2.LINE_AA)
    return img


def _panel(w=328, h=240, bgra=False):
    """Smooth colour gradient with vertical stripes and a diagonal bar: lots of structure."""
    import cv2
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.stack([60 + 120 * xx / w, 60 + 120 * yy / h, 100 + 60 * np.sin(xx / 7.0)], axis=2)
    img[(xx // 16) % 2 == 0] *= 0.7
    img = np.clip(img, 0, 255).astype(np.uint8)
    cv2.line(img, (0, 0), (w - 1, h - 1), (230, 230, 230), 5)
    if bgra:
        img = np.dstack([img, np.full((h, w), 255, np.uint8)])
    return img


def _quad_mask(shape, quad, erode=0):
    import cv2
    import numpy as np
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillConvexPoly(m, np.array(quad, np.int32), 255)
    if erode:
        m = cv2.erode(m, np.ones((2 * erode + 1, 2 * erode + 1), np.uint8))
    return m > 0


def _lum(img):
    import numpy as np
    return img.astype(np.float64) @ np.array([0.114, 0.587, 0.299])


@needs_cv
class CompositeTest(unittest.TestCase):
    def test_occluder_restored_exactly_and_panel_correlates(self):
        import cv2
        import numpy as np
        from tools.vidkit.screen import composite
        frame, panel = _scene(), _panel()
        occ = np.zeros(frame.shape[:2], bool)
        occ[150:230, 300:340] = True
        out = composite(frame, panel, CQUAD, occluder=occ)
        np.testing.assert_array_equal(out[occ], frame[occ])
        inner = _quad_mask(frame.shape, CQUAD, erode=3) & ~occ
        self.assertTrue((np.abs(out.astype(int) - frame.astype(int))[inner].max(axis=1) > 0).mean() > 0.95)
        m = cv2.getPerspectiveTransform(
            np.float32([[0, 0], [327, 0], [327, 239], [0, 239]]), np.float32(CQUAD))
        want = cv2.warpPerspective(panel, m, (640, 360), flags=cv2.INTER_LINEAR)
        a, b = _lum(out)[inner], _lum(want)[inner]
        corr = float(np.corrcoef(a, b)[0, 1])
        print("composite correlation %.4f" % corr)
        self.assertGreaterEqual(corr, 0.9)
        far = ~cv2.dilate(_quad_mask(frame.shape, CQUAD).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        np.testing.assert_array_equal(out[far], frame[far])

    def test_motion_blur_lowers_horizontal_gradient_energy(self):
        import cv2
        import numpy as np
        from tools.vidkit.screen import composite
        frame, panel = _scene(), _panel()
        prev = np.array(CQUAD) - [20.0, 0.0]
        inner = _quad_mask(frame.shape, CQUAD, erode=12)

        def energy(img):
            g = cv2.Sobel(_lum(img).astype(np.float32), cv2.CV_32F, 1, 0)
            return float((g[inner] ** 2).mean())
        still = energy(composite(frame, panel, CQUAD))
        moved = energy(composite(frame, panel, CQUAD, prev_corners=prev))
        print("gradient energy ratio %.3f" % (moved / still))
        self.assertLess(moved, 0.8 * still)

    def test_glass_zero_adds_no_residual(self):
        import numpy as np
        from tools.vidkit.screen import composite
        frame, panel = _scene(), _panel()
        # the original screen carries a texture: glass keeps its high frequencies on top
        rng = np.random.default_rng(2)
        noisy = frame.copy()
        inner = _quad_mask(frame.shape, CQUAD, erode=3)
        noisy[inner] = np.clip(noisy[inner].astype(int) + rng.integers(-40, 40, (int(inner.sum()), 3)), 0, 255)
        flat = composite(noisy, panel, CQUAD, glass=0.0)
        glassy = composite(noisy, panel, CQUAD, glass=0.2)
        self.assertGreater(np.abs(flat.astype(int) - glassy.astype(int))[inner].mean(), 0.5)
        # the difference is the original's high frequencies (original - blur, sigma 6) x glass
        import cv2
        resid = noisy.astype(np.float32) - cv2.GaussianBlur(noisy.astype(np.float32), (0, 0), 6)
        core = _quad_mask(frame.shape, CQUAD, erode=12)
        d = (glassy.astype(np.float32) - flat.astype(np.float32))
        corr = float(np.corrcoef(_lum(d)[core], _lum(resid)[core])[0, 1])
        print("glass residual correlation %.3f" % corr)
        self.assertGreaterEqual(corr, 0.9)

    def test_alpha_hole_shows_original(self):
        import numpy as np
        from tools.vidkit.screen import composite
        frame, panel = _scene(), _panel(bgra=True)
        panel[100:140, 144:184, 3] = 0
        out = composite(frame, panel, CQUAD, glass=0.0)
        # hole centre in panel = (164, 120), the panel centre -> inside the quad; the original there is green
        cx = int(np.mean([c[0] for c in CQUAD])); cy = int(np.mean([c[1] for c in CQUAD]))
        np.testing.assert_array_equal(out[cy - 2:cy + 2, cx - 2:cx + 2], frame[cy - 2:cy + 2, cx - 2:cx + 2])
        self.assertTrue((np.abs(out.astype(int) - frame.astype(int))[cy - 60:cy - 40, cx - 60:cx - 40]).max() > 0)

    def test_letterbox_when_aspect_differs(self):
        import numpy as np
        from tools.vidkit.screen import composite
        frame = _scene()
        wide = np.full((50, 400, 3), (40, 200, 240), np.uint8)   # 8:1 into a ~1.4:1 quad
        out = composite(frame, wide, CQUAD, glass=0.0)
        cx = int(np.mean([c[0] for c in CQUAD])); cy = int(np.mean([c[1] for c in CQUAD]))
        self.assertGreater(out[cy, cx, 2], 150)                   # panel colour (red channel)
        top = out[cy - 70, cx]                                    # near top of the quad: black bar
        self.assertLess(int(top.max()), 30)

    def test_shape_validation(self):
        from tools.vidkit.screen import composite
        with self.assertRaises(ValueError):
            composite(_scene(), _panel(), [[0, 0], [1, 1]])


def _write_clip(path, frames_bgr, fps=30, audio=True):
    """Encode BGR frames to H.264 mp4 (high quality), with a sine track when ``audio``."""
    import shutil
    import subprocess
    h, w = frames_bgr[0].shape[:2]
    cmd = [shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={len(frames_bgr) / fps}"]
    cmd += ["-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-shortest"] if audio else ["-an"]
    cmd.append(str(path))
    subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames_bgr), check=True, capture_output=True)
    return str(path)


def _green_frames(n=60, w=480, h=270, green=True):
    import cv2
    import numpy as np
    rng = np.random.default_rng(3)
    bg = cv2.GaussianBlur(rng.integers(80, 170, (h, w, 3), dtype=np.uint8), (0, 0), 2.0)
    out = []
    for t in range(n):
        f = bg.copy()
        if green:
            dx = t * 0.5
            quad = np.array([[140 + dx, 60], [340 + dx, 66], [334 + dx, 200], [136 + dx, 192]])
            cv2.fillPoly(f, [np.round(quad).astype(np.int32)], (0, 255, 0), cv2.LINE_AA)
        out.append(f)
    return out


@needs_cv
class InsertGreenTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        cv2 = __import__("cv2")
        self.panel = str(self.dir / "panel.png")
        cv2.imwrite(self.panel, _panel(w=200, h=134))
        self.addCleanup(self.tmp.cleanup)

    def test_green_end_to_end(self):
        import time
        import numpy as np
        from tools.vidkit import ff
        from tools.vidkit.screen import insert
        clip = _write_clip(self.dir / "in.mp4", _green_frames())
        out = str(self.dir / "out.mp4")
        t0 = time.time()
        res = insert(clip, self.panel, out, "green", qa_dir=str(self.dir / "qa"))
        print("green e2e %.1fs %s" % (time.time() - t0, res))
        a, b = ff.probe(clip), ff.probe(out)
        diff = abs(a["duration"] - b["duration"])
        print("duration diff %.4fs (frame %.4fs)" % (diff, 1 / 30))
        self.assertLessEqual(diff, 1 / 30 + 1e-6)
        self.assertEqual(res["frames"], 60)
        self.assertEqual(res["mode"], "green")
        self.assertIsNotNone(b["audio"])
        self.assertTrue((self.dir / "qa" / "qa-screen.jpg").is_file())
        import cv2
        cap = cv2.VideoCapture(out)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
        ok, f = cap.read()
        self.assertTrue(ok)
        px = f[133, 245].astype(int)       # quad centre at frame 30 (dx 15)
        print("centre pixel BGR", px.tolist())
        self.assertFalse(px[1] > 200 and px[0] < 60 and px[2] < 60, "still green")
        want = _panel(w=200, h=134)
        self.assertLess(float(np.abs(px - want[67, 100].astype(int) * 1.0).max()), 140)

    def test_no_green_refused(self):
        from tools.vidkit.screen import Refused, insert
        clip = _write_clip(self.dir / "plain.mp4", _green_frames(n=10, green=False), audio=False)
        with self.assertRaises(Refused) as cm:
            insert(clip, self.panel, str(self.dir / "o.mp4"), "green")
        self.assertEqual(str(cm.exception), "green key missing on 10 frames")

    def test_bad_inputs(self):
        from tools.vidkit.screen import insert
        clip = _write_clip(self.dir / "c.mp4", _green_frames(n=4), audio=False)
        with self.assertRaises(ValueError):
            insert(clip, self.panel, str(self.dir / "o.mp4"), "nope")
        with self.assertRaises(ValueError):
            insert(clip, self.panel, str(self.dir / "o.mp4"), "track")
        with self.assertRaises(FileNotFoundError):
            insert(clip, str(self.dir / "missing.png"), str(self.dir / "o.mp4"), "green")

    def test_panel_video_shorter_than_clip_loops_and_no_audio_clip(self):
        from tools.vidkit import ff
        from tools.vidkit.screen import insert
        clip = _write_clip(self.dir / "c.mp4", _green_frames(n=20), audio=False)
        pv = _write_clip(self.dir / "p.mp4", [_panel(w=200, h=134)] * 5, audio=False)
        out = str(self.dir / "o.mp4")
        res = insert(clip, pv, out, "green")
        self.assertEqual(res["frames"], 20)
        self.assertIsNone(ff.probe(out)["audio"])


@needs_ml
class InsertTrackTest(unittest.TestCase):
    def test_track_end_to_end(self):
        import tempfile
        import time
        from pathlib import Path
        import cv2
        from tools.vidkit import ff
        from tools.vidkit.screen import insert
        frames, truth = _synthetic(n=20)
        with tempfile.TemporaryDirectory() as d:
            clip = _write_clip(Path(d) / "t.mp4", [f[..., ::-1].copy() for f in frames], audio=False)
            panel = str(Path(d) / "p.png")
            cv2.imwrite(panel, _panel(w=170, h=110))
            out = str(Path(d) / "o.mp4")
            t0 = time.time()
            res = insert(clip, panel, out, "track", corners=truth[0].tolist(), occluder_point=[250, 180])
            print("track e2e %.1fs %s" % (time.time() - t0, res))
            self.assertTrue(Path(out).is_file())
            self.assertEqual(res["frames"], 20)
            self.assertLessEqual(abs(ff.probe(out)["duration"] - ff.probe(clip)["duration"]), 1 / 30 + 1e-6)
