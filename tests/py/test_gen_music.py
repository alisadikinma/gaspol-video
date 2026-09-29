import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from tools import asset_home, gen_music, renders
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


class HomeLibraryTest(unittest.TestCase):
    """The library defaults to GASPOL_VIDEO_HOME; recipes stay in the plugin (GV-8 K4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        env = patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home),
                                      "ELEVENLABS_API_KEY": "k"})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.palette = self.root / "palette.json"
        self.palette.write_text(json.dumps(PALETTE))

    def _run(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = gen_music.main(argv)
        return rc, out.getvalue()

    def test_default_library_is_home_and_recipes_come_from_the_flag(self):
        rc, out = self._run(["--recipes", str(self.palette), "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("WOULD generate tense-low-pulse -> tracks/tense-low-pulse.mp3", out)
        self.assertTrue((self.home / "library" / "music").is_dir())

    def test_default_recipes_are_the_plugins_palette(self):
        first = json.loads(asset_home.recipes("music").read_text())["moods"][0]["id"]
        rc, out = self._run(["--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn(f"WOULD generate {first}", out)

    def test_track_in_home_library_is_skipped(self):
        tracks = asset_home.library("music") / "tracks"
        tracks.mkdir()
        (tracks / "tense-low-pulse.mp3").write_bytes(b"x" * 10)
        rc, out = self._run(["--recipes", str(self.palette), "--dry-run"])
        self.assertIn("skipping (library-first): tense-low-pulse", out)

    def test_explicit_library_reads_its_own_palette_and_ignores_home(self):
        lib = self.root / "custom"
        lib.mkdir()
        (lib / "palette.json").write_text(json.dumps(
            {"moods": [{"id": "custom-only", "prompt": "p", "duration_s": 30}]}))
        rc, out = self._run(["--library", str(lib), "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("WOULD generate custom-only", out)
        self.assertFalse((self.home / "library").exists())

    def test_adopt_runs_before_a_real_run_but_not_a_dry_run(self):
        with patch.object(gen_music.asset_home, "adopt", return_value=0) as adopt, \
                patch("tools.gen_music.urllib.request.urlopen", side_effect=OSError("offline")):
            self._run(["--recipes", str(self.palette), "--dry-run"])
            adopt.assert_not_called()
            self._run(["--recipes", str(self.palette)])
            adopt.assert_called_once()
            self.assertEqual(adopt.call_args.args[0], "music")

    def test_video_defaults_still_read_the_plugin_palette(self):
        with patch.object(gen_music.asset_home, "recipes", return_value=self.palette) as rec:
            defaults = gen_music._plugin_defaults()
        rec.assert_called_once_with("music")
        self.assertEqual(defaults["model"], "music_v2")


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


KEY = "test-key-do-not-leak"
AUDIO = b"ID3" + b"\x00" * 4000


class FakeSender:
    def __init__(self, result=AUDIO, error=None):
        self.result, self.error, self.calls = result, error, []

    def __call__(self, url, headers, body, api_key):
        self.calls.append((url, headers, body, api_key))
        if self.error is not None:
            raise self.error
        return self.result


def http_error(code, body=b""):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))


class VideoMusicRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "output").mkdir()
        self.master = self.project / "output" / "master.mp4"
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_video(self, sender, extra=(), env=None):
        env = {"ELEVENLABS_API_KEY": KEY} if env is None else env
        rc = gen_music.main_video([str(self.project), *extra], sender=sender, env=env,
                                  log=self.logs.append)
        return rc, "\n".join(self.logs)

    def make_master(self, seconds=1.0):
        make_clip(self.master, seconds=seconds, size="640x360")

    def ledger(self):
        return renders.load(self.project)["renders"]

    @requires_ffmpeg
    def test_http_403_falls_back_with_exit_3(self):
        self.make_master()
        fake = FakeSender(error=http_error(403))
        rc, out = self.run_video(fake)
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: HTTP 403", out)

    @requires_ffmpeg
    def test_success_writes_file_and_done_ledger_entry(self):
        self.make_master()
        fake = FakeSender()
        rc, out = self.run_video(fake, ["--tags", "cinematic,tense"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][3], KEY)
        self.assertEqual((self.project / "output" / "music.mp3").read_bytes()[:3], b"ID3")
        self.assertIn('wrote output/music.mp3', out)
        self.assertIn('"bed_source": "video"', out)
        entry = self.ledger()[0]
        self.assertEqual((entry["file"], entry["phase"], entry["status"], entry["model"]),
                         ("output/music.mp3", "6", "done", "music_v2"))
        self.assertNotIn(KEY, (self.project / "renders.json").read_text())
        self.assertNotIn(KEY, out)
        self.assertFalse((self.project / ".tmp" / "music-proxy.mp4").exists())

    @requires_ffmpeg
    def test_second_run_with_same_master_is_up_to_date(self):
        self.make_master()
        self.run_video(FakeSender())
        fake = FakeSender()
        rc, out = self.run_video(fake)
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, [])
        self.assertIn("up-to-date: output/music.mp3 (master unchanged)", out)

    @requires_ffmpeg
    def test_changed_master_requests_again(self):
        self.make_master()
        self.run_video(FakeSender())
        self.make_master(seconds=1.5)
        fake = FakeSender()
        rc, _ = self.run_video(fake)
        self.assertEqual((rc, len(fake.calls)), (0, 1))

    @requires_ffmpeg
    def test_force_requests_again(self):
        self.make_master()
        self.run_video(FakeSender())
        fake = FakeSender()
        rc, _ = self.run_video(fake, ["--force"])
        self.assertEqual((rc, len(fake.calls)), (0, 1))

    @requires_ffmpeg
    def test_no_key_falls_back_without_request_or_ledger_entry(self):
        self.make_master()
        fake = FakeSender()
        rc, out = self.run_video(fake, env={})
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: ELEVENLABS_API_KEY not set", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.ledger(), [])

    def test_missing_ffmpeg_falls_back_without_request(self):
        self.make_master()
        fake = FakeSender()
        with patch("tools.gen_music.FFMPEG", None):
            rc, out = self.run_video(fake)
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: ffmpeg not found", out)
        self.assertEqual(fake.calls, [])

    def test_master_over_600s_falls_back_before_proxy(self):
        self.master.write_bytes(b"not really a video")
        fake = FakeSender()
        with patch("tools.gen_music.probe_duration", return_value=700.0), \
                patch("tools.gen_music.make_proxy", side_effect=AssertionError("no proxy")):
            rc, out = self.run_video(fake)
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: master is 700s, video-to-music accepts up to 600s", out)
        self.assertEqual(fake.calls, [])

    def test_missing_master_falls_back(self):
        rc, out = self.run_video(FakeSender())
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: master not found", out)

    @requires_ffmpeg
    def test_proxy_over_200mb_falls_back(self):
        self.make_master()
        fake = FakeSender()
        with patch("tools.gen_music.V2M_MAX_BYTES", 10):
            rc, out = self.run_video(fake)
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: proxy is", out)
        self.assertIn("limit 200 MB", out)
        self.assertEqual(fake.calls, [])

    @requires_ffmpeg
    def test_tiny_response_falls_back_with_failed_entry(self):
        self.make_master()
        rc, out = self.run_video(FakeSender(result=b"tiny"))
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: response too small (4 bytes)", out)
        entry = self.ledger()[0]
        self.assertEqual(entry["status"], "failed")
        self.assertIn("response too small", entry["error"])
        self.assertFalse((self.project / "output" / "music.mp3").exists())

    @requires_ffmpeg
    def test_http_422_reports_body_and_records_failed(self):
        self.make_master()
        rc, out = self.run_video(FakeSender(error=http_error(422, b"bad input " * 50)))
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: HTTP 422 \u2014 bad input", out)
        self.assertEqual(self.ledger()[0]["status"], "failed")

    @requires_ffmpeg
    def test_other_http_code_falls_back(self):
        self.make_master()
        rc, out = self.run_video(FakeSender(error=http_error(500, b"boom")))
        self.assertEqual(rc, 3)
        self.assertIn("FALLBACK palette: HTTP 500", out)

    @requires_ffmpeg
    def test_network_error_falls_back_once_with_certificate_hint(self):
        self.make_master()
        err = urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] nope")
        fake = FakeSender(error=err)
        rc, out = self.run_video(fake)
        self.assertEqual(rc, 3)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("Install Certificates.command", out)
        self.assertEqual(self.ledger()[0]["status"], "failed")

    @requires_ffmpeg
    def test_dry_run_checks_but_never_sends(self):
        self.make_master()
        fake = FakeSender()
        rc, out = self.run_video(fake, ["--dry-run", "--tags", "a,b"])
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, [])
        self.assertIn("WOULD request video-to-music:", out)
        self.assertIn("model music_v2, 2 tags", out)
        self.assertTrue((self.project / ".tmp" / "music-proxy.mp4").exists())
        self.assertEqual(self.ledger(), [])

    @requires_ffmpeg
    def test_too_many_tags_is_a_usage_error_not_a_crash(self):
        self.make_master()
        fake = FakeSender()
        rc, _ = self.run_video(fake, ["--tags", ",".join(f"t{i}" for i in range(11))])
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()


class DefaultTagsTest(unittest.TestCase):
    """Spec GV-8: with no --tags, style tags come from the project's tone."""

    def brief(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name)
        (project / "strategic-brief.md").write_text(text, encoding="utf-8")
        return project

    def test_tone_heading_gives_tone_plus_mood_descriptors(self):
        project = self.brief("# Brief\n\n## Tone: Serious\n\nDetail.\n")
        self.assertEqual(gen_music.default_tags(project),
                         ["serious", "low pulsing bed", "restrained", "industrial documentary"])

    def test_video_tone_field_is_read_too(self):
        project = self.brief("video_tone: Professional\n")
        self.assertEqual(gen_music.default_tags(project)[0], "professional")

    def test_negated_descriptors_never_become_tags(self):
        project = self.brief("## Tone: Serious\n")
        self.assertFalse([t for t in gen_music.default_tags(project) if t.startswith("no ")])

    def test_no_brief_or_unknown_tone_gives_no_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gen_music.default_tags(Path(tmp)), [])
        self.assertEqual(gen_music.default_tags(self.brief("## Tone: Whimsical\n")), [])
