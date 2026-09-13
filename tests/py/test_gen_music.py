import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import gen_music


PALETTE = {
    "_comment": "test palette",
    "defaults": {
        "model": "music_v2",
        "force_instrumental": True,
        "target_lufs": -20.0,
        "ceiling_dbfs": -1.5,
        "output_format": "mp3_44100_128",
    },
    "moods": [
        {"id": "tense-low-pulse", "tones": ["Serious"], "prompt": "low pulsing bed", "duration_s": 60},
        {"id": "sparse-ambient", "tones": ["Casual"], "prompt": "sparse ambient pad", "duration_s": 60},
    ],
}


class PlanWorkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = Path(self.tmp.name)
        (self.library / "tracks").mkdir(parents=True)
        (self.library / "palette.json").write_text(json.dumps(PALETTE))

    def tearDown(self):
        self.tmp.cleanup()

    def test_skips_mood_whose_track_exists(self):
        (self.library / "tracks" / "tense-low-pulse.mp3").write_bytes(b"x" * 10)
        todo, skipped = gen_music.plan_work(PALETTE, self.library)
        self.assertEqual([m["id"] for m in todo], ["sparse-ambient"])
        self.assertEqual(skipped, ["tense-low-pulse"])

    def test_force_includes_existing(self):
        (self.library / "tracks" / "tense-low-pulse.mp3").write_bytes(b"x" * 10)
        todo, skipped = gen_music.plan_work(PALETTE, self.library, force=True)
        self.assertEqual({m["id"] for m in todo}, {"tense-low-pulse", "sparse-ambient"})
        self.assertEqual(skipped, [])

    def test_only_filters(self):
        todo, skipped = gen_music.plan_work(PALETTE, self.library, only=["sparse-ambient"])
        self.assertEqual([m["id"] for m in todo], ["sparse-ambient"])

    def test_only_unknown_id_raises(self):
        with self.assertRaises(gen_music.MusicLibraryError) as ctx:
            gen_music.plan_work(PALETTE, self.library, only=["nonexistent-mood"])
        self.assertIn("unknown mood: nonexistent-mood", str(ctx.exception))


class BuildRequestTest(unittest.TestCase):
    def test_duration_from_mood(self):
        mood = {"id": "tense-low-pulse", "prompt": "low pulsing bed", "duration_s": 60}
        url, headers, body = gen_music.build_request(mood, PALETTE["defaults"])
        payload = json.loads(body)
        self.assertEqual(payload["music_length_ms"], 60000)
        self.assertEqual(payload["prompt"], "low pulsing bed")
        self.assertNotIn("xi-api-key", {k.lower(): v for k, v in headers.items()})

    def test_length_s_overrides_duration(self):
        mood = {"id": "tense-low-pulse", "prompt": "low pulsing bed", "duration_s": 60}
        url, headers, body = gen_music.build_request(mood, PALETTE["defaults"], length_s=90)
        payload = json.loads(body)
        self.assertEqual(payload["music_length_ms"], 90000)


class GainForTest(unittest.TestCase):
    def test_normal_gain(self):
        self.assertAlmostEqual(gen_music.gain_for(-26, -8, -20, -1.5), 6.0, places=2)

    def test_clamped_gain(self):
        self.assertAlmostEqual(gen_music.gain_for(-26, -3, -20, -1.5), 1.5, places=2)

    def test_silent_track_uses_ceiling_minus_peak(self):
        self.assertAlmostEqual(gen_music.gain_for(None, -8, -20, -1.5), 6.5, places=2)


class MissingPaletteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = Path(self.tmp.name)  # no palette.json written

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_palette_raises_when_missing(self):
        with self.assertRaises(gen_music.MusicLibraryError) as ctx:
            gen_music.load_palette(self.library)
        self.assertIn("palette not found", str(ctx.exception))
        self.assertIn(str(self.library), str(ctx.exception))

    def test_generate_raises_named_error_when_palette_missing(self):
        with self.assertRaises(gen_music.MusicLibraryError) as ctx:
            gen_music.generate(self.library, env={"ELEVENLABS_API_KEY": "x"})
        self.assertIn("palette not found", str(ctx.exception))

    def test_main_exits_1_when_palette_missing(self):
        rc = gen_music.main(["--library", str(self.library), "--dry-run"])
        self.assertEqual(rc, 1)


class RequestFailureWrappingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = Path(self.tmp.name)
        (self.library / "tracks").mkdir(parents=True)
        (self.library / "palette.json").write_text(json.dumps(PALETTE))

    def tearDown(self):
        self.tmp.cleanup()

    def test_certificate_verify_failed_mentions_the_fix(self):
        with patch("tools.gen_music.urllib.request.urlopen",
                   side_effect=urllib.error.URLError(
                       "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")):
            with self.assertRaises(gen_music.MusicLibraryError) as ctx:
                gen_music.generate(self.library, env={"ELEVENLABS_API_KEY": "fake-key"})
        self.assertIn("CERTIFICATE_VERIFY_FAILED", str(ctx.exception))
        self.assertIn("Install Certificates", str(ctx.exception))

    def test_plain_url_error_is_wrapped_without_certificate_hint(self):
        with patch("tools.gen_music.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("network down")):
            with self.assertRaises(gen_music.MusicLibraryError) as ctx:
                gen_music.generate(self.library, env={"ELEVENLABS_API_KEY": "fake-key"})
        self.assertIn("network down", str(ctx.exception))
        self.assertNotIn("Install Certificates", str(ctx.exception))

    def test_os_error_is_wrapped(self):
        with patch("tools.gen_music.urllib.request.urlopen", side_effect=OSError("disk full")):
            with self.assertRaises(gen_music.MusicLibraryError) as ctx:
                gen_music.generate(self.library, env={"ELEVENLABS_API_KEY": "fake-key"})
        self.assertIn("disk full", str(ctx.exception))


class DryRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.library = Path(self.tmp.name)
        (self.library / "tracks").mkdir(parents=True)
        (self.library / "palette.json").write_text(json.dumps(PALETTE))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_makes_no_request(self):
        with patch("tools.gen_music.urllib.request.urlopen",
                   side_effect=AssertionError("must not be called")):
            result = gen_music.generate(
                self.library, env={"ELEVENLABS_API_KEY": "fake-key"}, dry_run=True
            )
        self.assertEqual(result["written"], [])


if __name__ == "__main__":
    unittest.main()
