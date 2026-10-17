import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tests.py.media import requires_ffmpeg
from tools.vidkit import __main__ as vcli
from tools.vidkit import ff, reframe


class KeysTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(reframe.parse_keys("0:0.2, 1.5:0.8"), [(0.0, 0.2), (1.5, 0.8)])

    def test_parse_rejects_bad_input(self):
        for bad in ("", "0:1.2", "1:0.5,0.5:0.4", "x:0.5", "0.5"):
            with self.assertRaises(ValueError, msg=bad):
                reframe.parse_keys(bad)

    def test_center_interpolates_and_holds_at_ends(self):
        keys = [(1.0, 0.2), (3.0, 0.6)]
        self.assertAlmostEqual(reframe.center_at(keys, 0.0), 0.2)
        self.assertAlmostEqual(reframe.center_at(keys, 2.0), 0.4)
        self.assertAlmostEqual(reframe.center_at(keys, 9.0), 0.6)

    def test_window_is_9x16_and_clamped(self):
        w, h = reframe.window(3840, 2160, zoom=1.0)
        self.assertEqual((w, h), (1214, 2160))  # even, 9:16
        w2, h2 = reframe.window(3840, 2160, zoom=2.0)
        self.assertEqual((w2, h2), (606, 1080))
        with self.assertRaises(ValueError):
            reframe.window(3840, 2160, zoom=0.5)

    def test_x_expression_matches_python_center(self):
        keys = [(0.0, 0.1), (2.0, 0.9)]
        expr = reframe.x_expr(keys, 1000, 200)
        for t in (0.0, 0.5, 1.0, 2.0, 3.0):
            want = min(max(reframe.center_at(keys, t) * 1000 - 100, 0), 800)
            got = eval(expr.replace("if(", "_if(").replace("lt(", "_lt(")
                       .replace("clip(", "_clip("), {"_if": lambda c, a, b: a if c else b,
                                                     "_lt": lambda a, b: a < b,
                                                     "_clip": lambda v, lo, hi: min(max(v, lo), hi),
                                                     "t": t})
            self.assertAlmostEqual(got, want, places=3, msg=t)


class ApplyTest(unittest.TestCase):
    def _clip(self, d):
        # a white box moving left to right over 2 s on a 640x360 black frame
        src = Path(d) / "wide.mp4"
        ff.ffmpeg("-f", "lavfi", "-i", "color=c=black:s=640x360:d=2:r=25",
                  "-f", "lavfi", "-i", "color=c=white:s=60x60:d=2:r=25",
                  "-filter_complex", "[0][1]overlay=x='200+120*t':y=150",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", src)
        return src

    def _center_luma(self, path, t):
        raw = ff.run_bytes(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                      "-vf", "crop=20:20:(iw-20)/2:(ih-20)/2,scale=1:1", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"])
        return raw[0]

    @requires_ffmpeg
    def test_window_follows_the_subject(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = self._clip(d), Path(d) / "tall.mp4"
            # box centre x = 230 + 120 t, kept clear of the edges so the window is never clamped
            reframe.apply(str(src), str(out), [(0.0, 230 / 640), (2.0, 470 / 640)], size=(360, 640))
            p = ff.probe(str(out))
            self.assertEqual((p["video"]["width"], p["video"]["height"]), (360, 640))
            self.assertAlmostEqual(p["video"]["duration"], 2.0, delta=0.1)
            for t in (0.2, 1.0, 1.8):
                self.assertGreater(self._center_luma(out, t), 200, msg=t)

    @requires_ffmpeg
    def test_refuses_to_overwrite_its_source(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._clip(d)
            with self.assertRaises(ValueError):
                reframe.apply(str(src), str(src), [(0, 0.5)])

    @requires_ffmpeg
    def test_fit_keeps_the_whole_frame_centred(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = self._clip(d), Path(d) / "fit.mp4"
            reframe.fit(str(src), str(out), size=(360, 640))
            p = ff.probe(str(out))
            self.assertEqual((p["video"]["width"], p["video"]["height"]), (360, 640))
            self.assertAlmostEqual(p["video"]["duration"], 2.0, delta=0.1)

    @requires_ffmpeg
    def test_cli_needs_keys_or_fit(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._clip(d)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = vcli.main(["reframe", str(src), str(Path(d) / "x.mp4")])
            self.assertNotEqual(rc, 0)

    @requires_ffmpeg
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = self._clip(d), Path(d) / "tall.mp4"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["reframe", str(src), str(out), "--keys", "0:0.2,2:0.8",
                                "--size", "360x640"])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
