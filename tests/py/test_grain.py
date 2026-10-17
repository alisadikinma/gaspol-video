import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from tests.py.media import requires_ffmpeg
from tools.vidkit import __main__ as vcli
from tools.vidkit import ff, grain


def _ystd(path):
    """Mean luma spread inside one frame (signalstats YHIGH-YLOW) — grain widens it on a flat frame."""
    err = ff.run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "signalstats,metadata=print",
                  "-frames:v", "5", "-f", "null", "-"], capture_stderr=True)
    hi = [float(v) for v in re.findall(r"YHIGH=([\d.]+)", err)]
    lo = [float(v) for v in re.findall(r"YLOW=([\d.]+)", err)]
    return sum(h - l for h, l in zip(hi, lo)) / len(hi)


class FilterTest(unittest.TestCase):
    def test_filter_is_temporal_noise(self):
        self.assertEqual(grain.vf(8), "noise=alls=8:allf=t")

    def test_strength_out_of_range_rejected(self):
        for bad in (0, -1, 41):
            with self.assertRaises(ValueError):
                grain.vf(bad)


class ApplyTest(unittest.TestCase):
    def _clip(self, d):
        src = Path(d) / "flat.mp4"
        ff.ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=128x128:d=2:r=25",
                  "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest",
                  "-c:v", "libx264", "-crf", "12", "-c:a", "aac", src)
        return src

    @requires_ffmpeg
    def test_adds_texture_keeps_length_and_audio(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = self._clip(d), Path(d) / "g.mp4"
            grain.apply(str(src), str(out), strength=10)
            p, q = ff.probe(str(src)), ff.probe(str(out))
            self.assertAlmostEqual(q["video"]["duration"], p["video"]["duration"], delta=0.05)
            self.assertIsNotNone(q["audio"])
            self.assertAlmostEqual(q["audio"]["duration"], p["audio"]["duration"], delta=0.05)
            self.assertGreater(_ystd(out), _ystd(src) + 5)

    @requires_ffmpeg
    def test_refuses_to_overwrite_its_source(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._clip(d)
            with self.assertRaises(ValueError):
                grain.apply(str(src), str(src))

    @requires_ffmpeg
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = self._clip(d), Path(d) / "g.mp4"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["grain", str(src), str(out), "--strength", "6"])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
