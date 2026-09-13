import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.py.media import duration_of, make_clip, requires_ffmpeg
from tools import clean_voice


class LevelGainTest(unittest.TestCase):
    def test_clamped_gain(self):
        # unclamped gain would be 6.0 (-20 - -26); clean_peak -4 + 6.0 = 2.0 > -1.0 ceiling,
        # so it is clamped to -1.0 - -4 = 3.0.
        self.assertAlmostEqual(clean_voice.level_gain(-20, -26, -4, -1.0), 3.0)

    def test_unclamped_gain(self):
        # clean_peak -10 + 6.0 = -4.0, which is under the -1.0 ceiling — no clamp needed.
        self.assertAlmostEqual(clean_voice.level_gain(-20, -26, -10, -1.0), 6.0)


class ModelPathTest(unittest.TestCase):
    def test_known_model(self):
        p = clean_voice.model_path("sh")
        self.assertTrue(p.exists(), f"{p} should exist (committed .rnnn asset)")

    def test_unknown_model_raises(self):
        with self.assertRaises(clean_voice.CleanError):
            clean_voice.model_path("xx")

    def test_bd_was_dropped(self):
        # bd.rnnn was a 14-byte "404: Not Found" page (broken upstream too) — dropped, not shipped.
        with self.assertRaises(clean_voice.CleanError):
            clean_voice.model_path("bd")


class ShippedModelsAreRealTest(unittest.TestCase):
    def test_every_shipped_rnnn_is_larger_than_100kb(self):
        files = list(clean_voice.MODELS_DIR.glob("*.rnnn"))
        self.assertTrue(files, "expected at least one .rnnn model to be shipped")
        for f in files:
            self.assertGreater(
                f.stat().st_size, 100_000,
                f"{f} is only {f.stat().st_size} bytes — looks like a broken/404 download, not a real model",
            )


class MultipartBodyTest(unittest.TestCase):
    def test_contains_field_name_and_bytes(self):
        body = clean_voice.multipart_body("audio", "in.wav", b"\x00\x01FAKEBYTES", "BOUNDARY123")
        self.assertIn(b'name="audio"', body)
        self.assertIn(b"FAKEBYTES", body)
        self.assertIn(b"--BOUNDARY123--", body)


class CleanRefusesOverwriteTest(unittest.TestCase):
    def test_same_in_out_path_refused(self):
        with self.assertRaises(clean_voice.CleanError) as ctx:
            clean_voice.clean("same.mp4", "same.mp4", method="rnnoise")
        self.assertIn("overwrite", str(ctx.exception).lower())


class CleanRnnoiseRealRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @requires_ffmpeg
    def test_rnnoise_keeps_duration_and_copies_video_codec(self):
        src = make_clip(self.dir / "in.mp4", seconds=2.0)
        out = self.dir / "out.mp4"
        result = clean_voice.clean(src, out, method="rnnoise", model="sh")
        self.assertEqual(result, str(out))
        self.assertTrue(out.exists())
        in_dur = duration_of(src, "v:0")
        out_dur = duration_of(out, "v:0")
        self.assertAlmostEqual(in_dur, out_dur, delta=0.05)

        import subprocess
        codec_in = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(src)],
            capture_output=True, text=True,
        ).stdout.strip()
        codec_out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(codec_in, codec_out, "video stream must be copied, not re-encoded")

    @requires_ffmpeg
    def test_source_file_is_never_modified(self):
        src = make_clip(self.dir / "in.mp4", seconds=2.0)
        mtime_before = src.stat().st_mtime if hasattr(src, "stat") else Path(src).stat().st_mtime
        out = self.dir / "out.mp4"
        clean_voice.clean(src, out, method="rnnoise", model="sh")
        mtime_after = Path(src).stat().st_mtime
        self.assertEqual(mtime_before, mtime_after)

    @requires_ffmpeg
    def test_duration_gate_removes_output_and_raises(self):
        src = make_clip(self.dir / "in.mp4", seconds=2.0)
        out = self.dir / "out.mp4"
        with mock.patch.object(clean_voice, "duration_of", side_effect=[2.0, 2.2]):
            with self.assertRaises(clean_voice.CleanError) as ctx:
                clean_voice.clean(src, out, method="rnnoise", model="sh")
        self.assertIn("duration changed", str(ctx.exception))
        self.assertFalse(out.exists(), "the drifted output must be deleted, not left behind")

    @requires_ffmpeg
    def test_unmeasurable_source_duration_refuses_rather_than_accepting(self):
        src = make_clip(self.dir / "in.mp4", seconds=2.0)
        out = self.dir / "out.mp4"
        with mock.patch.object(clean_voice, "duration_of", side_effect=[None, 2.0]):
            with self.assertRaises(clean_voice.CleanError) as ctx:
                clean_voice.clean(src, out, method="rnnoise", model="sh")
        self.assertIn("cannot measure duration", str(ctx.exception))
        self.assertIn("lip-sync", str(ctx.exception))
        self.assertFalse(out.exists(), "an unverifiable output must not be left behind")

    @requires_ffmpeg
    def test_unmeasurable_output_duration_refuses_rather_than_accepting(self):
        src = make_clip(self.dir / "in.mp4", seconds=2.0)
        out = self.dir / "out.mp4"
        with mock.patch.object(clean_voice, "duration_of", side_effect=[2.0, None]):
            with self.assertRaises(clean_voice.CleanError) as ctx:
                clean_voice.clean(src, out, method="rnnoise", model="sh")
        self.assertIn("cannot measure duration", str(ctx.exception))
        self.assertFalse(out.exists(), "an unverifiable output must not be left behind")


if __name__ == "__main__":
    unittest.main()
