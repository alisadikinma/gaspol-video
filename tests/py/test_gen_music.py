import json
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import gen_music
from tests.py.media import duration_of, make_clip, requires_ffmpeg


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


class VideoMusicRequestTest(unittest.TestCase):
    def test_request_shape(self):
        url, headers, body = gen_music.build_video_music_request(
            b"VID", "tense low pulse", ["cinematic"], "music_v2")
        self.assertTrue(url.endswith("/v1/music/video-to-music?output_format=mp3_44100_128"))
        self.assertTrue(headers["Content-Type"].startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="videos"; filename="master.mp4"', body)
        self.assertIn(b"Content-Type: video/mp4", body)
        self.assertIn(b"VID", body)
        self.assertIn(b'name="description"', body)
        self.assertIn(b"tense low pulse", body)
        self.assertEqual(body.count(b'name="tags"'), 1)
        self.assertIn(b'name="model_id"', body)
        self.assertIn(b"music_v2", body)
        self.assertNotIn("xi-api-key", {k.lower() for k in headers})
        self.assertNotIn(b"xi-api-key", body)


    def test_eleven_tags_refused(self):
        with self.assertRaises(gen_music.MusicLibraryError) as ctx:
            gen_music.build_video_music_request(b"V", "d", [f"t{i}" for i in range(11)], "music_v2")
        self.assertIn("tags", str(ctx.exception))

    def test_ten_tags_become_ten_fields(self):
        _, _, body = gen_music.build_video_music_request(
            b"V", "d", [f"t{i}" for i in range(10)], "music_v2")
        self.assertEqual(body.count(b'name="tags"'), 10)

    def test_unknown_model_refused(self):
        with self.assertRaises(gen_music.MusicLibraryError) as ctx:
            gen_music.build_video_music_request(b"V", "d", [], "music_v9")
        self.assertIn("music_v9", str(ctx.exception))

    def test_overlong_description_refused(self):
        with self.assertRaises(gen_music.MusicLibraryError):
            gen_music.build_video_music_request(b"V", "x" * 1001, [], "music_v2")

    def test_no_description_omits_the_field(self):
        _, _, body = gen_music.build_video_music_request(b"V", None, [], "music_v2")
        self.assertNotIn(b'name="description"', body)


class DefaultDescriptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_music_lines_and_table_column(self):
        (self.project / "av-script.md").write_text(
            "# Script\n"
            "Music: low pulsing bed, tense\n"
            "- musik: opens sparse, lifts at the reveal\n"
            "Narration: not music\n"
            "\n"
            "| Scene | Narration | Music |\n"
            "|---|---|---|\n"
            "| 1 | hello | soft piano |\n"
            "| 2 | world | - |\n"
        )
        self.assertEqual(
            gen_music.default_description(self.project),
            "low pulsing bed, tense; opens sparse, lifts at the reveal; soft piano")

    def test_truncates_on_a_word_boundary(self):
        (self.project / "av-script.md").write_text("Music: " + " ".join(["bed"] * 400) + "\n")
        out = gen_music.default_description(self.project)
        self.assertLessEqual(len(out), 1000)
        self.assertTrue(out.endswith("bed"))
        self.assertNotIn("  ", out)

    def test_none_found_returns_none(self):
        (self.project / "av-script.md").write_text("Narration: hello\n")
        self.assertIsNone(gen_music.default_description(self.project))

    def test_missing_script_returns_none(self):
        self.assertIsNone(gen_music.default_description(self.project))


class VideoDispatchTest(unittest.TestCase):
    def test_video_help_exits_0(self):
        with self.assertRaises(SystemExit) as ctx:
            gen_music.main(["video", "--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_video_routes_to_main_video(self):
        with patch("tools.gen_music.main_video", return_value=7) as mv:
            self.assertEqual(gen_music.main(["video", "proj", "--dry-run"]), 7)
        mv.assert_called_once_with(["proj", "--dry-run"])

    def test_palette_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            (library / "tracks").mkdir()
            (library / "palette.json").write_text(json.dumps(PALETTE))
            with patch("tools.gen_music.main_video", side_effect=AssertionError("not video")):
                self.assertEqual(gen_music.main(["--library", str(library), "--dry-run"]), 0)


class MakeProxyTest(unittest.TestCase):
    @requires_ffmpeg
    def test_proxy_is_picture_only_and_at_most_1280(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = make_clip(Path(tmp) / "master.mp4", seconds=1.0, size="1920x1080")
            dest = Path(tmp) / ".tmp" / "music-proxy.mp4"
            gen_music.make_proxy(master, dest)
            self.assertTrue(dest.exists())
            self.assertIsNone(duration_of(dest, "a:0"))
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width", "-of", "csv=p=0", str(dest)],
                capture_output=True, text=True)
            self.assertEqual(probe.stdout.strip(), "1280")


if __name__ == "__main__":
    unittest.main()
