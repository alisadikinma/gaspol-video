import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.py.media import requires_ffmpeg
from tests.py.test_prosody import write_wav
from tools.vidkit import __main__ as vcli
from tools.vidkit import ff, tighten


class PlanCutsTest(unittest.TestCase):
    def test_long_gap_is_cut_to_keep(self):
        words = [("a", 0.0, 1.0), ("b", 1.8, 2.5)]
        cuts = tighten.plan_cuts(words, max_gap=0.3, keep=0.2)
        self.assertEqual(len(cuts), 1)
        a, b = cuts[0]
        self.assertAlmostEqual(b - a, 0.6)          # 0.8 gap -> 0.2 kept
        self.assertAlmostEqual(a, 1.1)               # half the kept air stays after "a"

    def test_short_gaps_untouched(self):
        self.assertEqual(tighten.plan_cuts([("a", 0, 1), ("b", 1.2, 2)], max_gap=0.3, keep=0.2), [])

    def test_keep_must_not_exceed_max_gap(self):
        with self.assertRaises(ValueError):
            tighten.plan_cuts([], max_gap=0.2, keep=0.3)


class ApplyTest(unittest.TestCase):
    @requires_ffmpeg
    def test_output_is_shorter_by_the_cut(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "a.wav", Path(d) / "b.wav"
            write_wav(src, [(1.0, 200, 0.5), (0.8, 0, 0), (0.7, 200, 0.5)])
            words = [("a", 0.0, 1.0), ("b", 1.8, 2.5)]
            r = tighten.apply(str(src), words, str(out), max_gap=0.3, keep=0.2)
            self.assertEqual(r["cuts"], 1)
            self.assertAlmostEqual(ff.probe(str(out))["duration"], 1.9, delta=0.03)

    @requires_ffmpeg
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            src, out, wj = Path(d) / "a.wav", Path(d) / "b.wav", Path(d) / "w.json"
            write_wav(src, [(1.0, 200, 0.5), (0.8, 0, 0), (0.7, 200, 0.5)])
            wj.write_text(json.dumps([["a", 0.0, 1.0], ["b", 1.8, 2.5]]))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = vcli.main(["tighten", str(src), str(wj), str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
