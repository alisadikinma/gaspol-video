"""check_vo_duration and track_screen read media facts through vidkit.ff only."""
import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import (burn_subs, check_vo_duration, clean_voice, edit_render, gen_music, make_stems, mix_music, mix_sfx, overlay_plan,
                   qa_frames, track_screen)
from tools.vidkit import ff

HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SRC = {n: Path(m.__file__).read_text() for n, m in
       (("vo", check_vo_duration), ("ts", track_screen))}


class NoDirectProbe(unittest.TestCase):
    def test_sources_do_not_name_the_probe_binary(self):
        for name, text in SRC.items():
            self.assertNotIn("ffprobe", text, name)

    def test_modules_expose_vidkit_ff(self):
        self.assertIs(check_vo_duration.ff, ff)
        self.assertIs(track_screen.ff, ff)


class VoDuration(unittest.TestCase):
    def test_uses_probe_duration(self):
        with mock.patch.object(check_vo_duration.ff, "probe",
                               return_value={"duration": 4.25, "video": None, "audio": None}) as p:
            self.assertEqual(check_vo_duration.duration(Path("a.mp3")), 4.25)
        p.assert_called_once()

    def test_no_duration_is_zero_as_before(self):
        with mock.patch.object(check_vo_duration.ff, "probe",
                               return_value={"duration": None, "video": None, "audio": None}):
            self.assertEqual(check_vo_duration.duration(Path("a.mp3")), 0.0)

    def test_probe_failure_propagates(self):
        with mock.patch.object(check_vo_duration.ff, "probe", side_effect=ff.FFError("boom")):
            with self.assertRaises(ff.FFError):
                check_vo_duration.duration(Path("a.mp3"))


class TrackScreen(unittest.TestCase):
    def test_size_from_probe_video(self):
        info = {"duration": 2.0, "audio": None,
                "video": {"duration": 2.0, "fps": 25.0, "width": 640, "height": 360}}
        with mock.patch.object(track_screen.ff, "probe", return_value=info):
            self.assertEqual(track_screen.probe_size(Path("c.mp4")), (640, 360))

    def test_no_video_stream_raises(self):
        info = {"duration": 2.0, "video": None, "audio": None}
        with mock.patch.object(track_screen.ff, "probe", return_value=info):
            with self.assertRaises(ff.FFError):
                track_screen.probe_size(Path("c.mp3"))

    def test_duration_from_probe(self):
        info = {"duration": 3.5, "video": None, "audio": None}
        with mock.patch.object(track_screen.ff, "probe", return_value=info):
            self.assertEqual(track_screen.probe_duration(Path("c.mp4")), 3.5)

    def test_no_duration_is_zero_as_before(self):
        info = {"duration": None, "video": None, "audio": None}
        with mock.patch.object(track_screen.ff, "probe", return_value=info):
            self.assertEqual(track_screen.probe_duration(Path("c.mp4")), 0.0)

    def test_probe_failure_propagates(self):
        with mock.patch.object(track_screen.ff, "probe", side_effect=ff.FFError("boom")):
            with self.assertRaises(ff.FFError):
                track_screen.probe_size(Path("c.mp4"))
            with self.assertRaises(ff.FFError):
                track_screen.probe_duration(Path("c.mp4"))


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class RealFiles(unittest.TestCase):
    def test_real_clip_values(self):
        with tempfile.TemporaryDirectory() as d:
            clip = Path(d) / "c.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=white:s=320x180:d=1.5:r=25", "-f", "lavfi", "-i",
                            "sine=d=1.5", "-shortest", "-pix_fmt", "yuv420p", str(clip)],
                           check=True)
            self.assertEqual(track_screen.probe_size(clip), (320, 180))
            self.assertAlmostEqual(track_screen.probe_duration(clip), 1.5, delta=0.1)
            self.assertAlmostEqual(check_vo_duration.duration(clip), 1.5, delta=0.1)

    def test_missing_file_raises(self):
        with self.assertRaises(ff.FFError):
            check_vo_duration.duration(Path("/nonexistent/x.mp3"))


DURATION_TOOLS = {
    "gen_music": gen_music, "make_stems": make_stems, "mix_music": mix_music,
    "mix_sfx": mix_sfx, "overlay_plan": overlay_plan,
}


class DurationToolsNoDirectProbe(unittest.TestCase):
    def test_sources_do_not_name_the_probe_binary(self):
        for name, mod in DURATION_TOOLS.items():
            self.assertIsNone(re.search(r"\bffprobe\b", Path(mod.__file__).read_text()), name)

    def test_modules_expose_vidkit_ff(self):
        for name, mod in DURATION_TOOLS.items():
            self.assertIs(mod.ff, ff, name)


def _duration_calls():
    """(label, call(path)) for the five wrappers; make_stems raises where the rest return None."""
    return [
        ("gen_music", gen_music.probe_duration),
        ("mix_music", mix_music.duration_of),
        ("mix_sfx", mix_sfx.master_duration),
        ("overlay_plan", lambda p: overlay_plan._clip_duration(p)),
    ]


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class DurationToolsReal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.clip = self.dir / "c.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=white:s=160x90:d=1:r=25", "-f", "lavfi", "-i", "sine=d=1",
                        "-shortest", "-pix_fmt", "yuv420p", str(self.clip)], check=True)
        self.bad = self.dir / "bad.mp4"
        self.bad.write_text("not media")
        self.empty_path = self.dir / "emptybin"
        self.empty_path.mkdir()

    def test_value_on_real_clip(self):
        for label, call in _duration_calls():
            self.assertAlmostEqual(call(self.clip), 1.0, delta=0.1, msg=label)
        self.assertAlmostEqual(make_stems._duration_of(self.clip), 1.0, delta=0.1)

    def test_gen_music_rounds_to_three_places(self):
        value = gen_music.probe_duration(self.clip)
        self.assertEqual(value, round(value, 3))

    def test_missing_binary_returns_none(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.empty_path)}):
            for label, call in _duration_calls():
                with self.subTest(label):
                    self.assertIsNone(call(self.clip))

    def test_make_stems_missing_binary_raises_stem_error(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.empty_path)}):
            with self.assertRaises(make_stems.StemError) as cm:
                make_stems._duration_of(self.clip)
        self.assertEqual(str(cm.exception), "ffprobe not found on PATH")

    def test_unreadable_returns_none(self):
        for label, call in _duration_calls():
            self.assertIsNone(call(self.bad), label)

    def test_make_stems_unreadable_raises_stem_error(self):
        with self.assertRaises(make_stems.StemError) as cm:
            make_stems._duration_of(self.bad)
        self.assertEqual(str(cm.exception), "bad.mp4: unreadable duration")

    def test_make_stems_no_duration_raises_stem_error(self):
        info = {"duration": None, "video": None, "audio": None}
        with mock.patch.object(make_stems.ff, "probe", return_value=info):
            with self.assertRaises(make_stems.StemError) as cm:
                make_stems._duration_of(self.clip)
        self.assertEqual(str(cm.exception), "c.mp4: unreadable duration")


STREAM_TOOLS = {
    "burn_subs": burn_subs, "clean_voice": clean_voice, "edit_render": edit_render,
    "qa_frames": qa_frames,
}


class StreamToolsNoDirectProbe(unittest.TestCase):
    def test_sources_do_not_name_the_probe_binary(self):
        for name, mod in STREAM_TOOLS.items():
            self.assertIsNone(re.search(r"\bffprobe\b", Path(mod.__file__).read_text()), name)

    def test_modules_expose_vidkit_ff(self):
        for name, mod in STREAM_TOOLS.items():
            self.assertIs(mod.ff, ff, name)


@unittest.skipUnless(HAVE_FF, "ffmpeg/ffprobe not installed")
class StreamToolsReal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.clip = self.dir / "c.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=white:s=160x90:d=1:r=25", "-f", "lavfi", "-i", "sine=d=1",
                        "-shortest", "-pix_fmt", "yuv420p", str(self.clip)], check=True)
        self.audio = self.dir / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1",
                        str(self.audio)], check=True)
        self.bad = self.dir / "bad.mp4"
        self.bad.write_text("not media")
        self.empty_path = self.dir / "emptybin"
        self.empty_path.mkdir()

    def no_path(self):
        return mock.patch.dict(os.environ, {"PATH": str(self.empty_path)})

    # burn_subs.video_height_of
    def test_burn_subs_height_value(self):
        self.assertEqual(burn_subs.video_height_of(self.clip), 90)

    def test_burn_subs_height_missing_and_unreadable_default_1080(self):
        with self.no_path():
            self.assertEqual(burn_subs.video_height_of(self.clip), 1080)
        self.assertEqual(burn_subs.video_height_of(self.bad), 1080)
        self.assertEqual(burn_subs.video_height_of(self.audio), 1080)

    # clean_voice
    def test_clean_voice_duration_value_and_unreadable(self):
        self.assertAlmostEqual(clean_voice.duration_of(self.clip), 1.0, delta=0.1)
        self.assertIsNone(clean_voice.duration_of(self.bad))

    def test_clean_voice_missing_raises_clean_error(self):
        with self.no_path():
            for call in (clean_voice.duration_of, clean_voice.has_audio_stream):
                with self.assertRaises(clean_voice.CleanError) as cm:
                    call(self.clip)
                self.assertEqual(str(cm.exception), "ffprobe not found on PATH")

    def test_clean_voice_has_audio_stream(self):
        self.assertTrue(clean_voice.has_audio_stream(self.clip))
        self.assertTrue(clean_voice.has_audio_stream(self.audio))
        self.assertFalse(clean_voice.has_audio_stream(self.bad))

    # edit_render
    def test_edit_render_duration_values(self):
        self.assertAlmostEqual(edit_render._probe_duration(self.clip), 1.0, delta=0.1)
        self.assertAlmostEqual(edit_render._probe_duration_stream(self.clip, "v:0"), 1.0, delta=0.1)
        self.assertAlmostEqual(edit_render._probe_duration_stream(self.clip, "a:0"), 1.0, delta=0.1)

    def test_edit_render_audio_only_has_no_video_stream(self):
        self.assertIsNone(edit_render._probe_duration_stream(self.audio, "v:0"))

    def test_edit_render_missing_and_unreadable_return_none(self):
        with self.no_path():
            self.assertIsNone(edit_render._probe_duration(self.clip))
            self.assertIsNone(edit_render._probe_duration_stream(self.clip, "v:0"))
        self.assertIsNone(edit_render._probe_duration(self.bad))
        self.assertIsNone(edit_render._probe_duration_stream(self.bad, "a:0"))

    # qa_frames
    def test_qa_frames_probe_value(self):
        duration, fps = qa_frames.probe(self.clip)
        self.assertAlmostEqual(duration, 1.0, delta=0.1)
        self.assertAlmostEqual(fps, 25.0, delta=0.01)

    def test_qa_frames_probe_unreadable(self):
        self.assertEqual(qa_frames.probe(self.bad), (None, 25.0))

    def test_qa_frames_probe_audio_only_uses_format_duration(self):
        duration, fps = qa_frames.probe(self.audio)
        self.assertAlmostEqual(duration, 1.0, delta=0.1)
        self.assertEqual(fps, qa_frames.DEFAULT_FPS)

    def test_qa_frames_main_missing_tools_exit_2(self):
        shutil.copy(self.clip, self.dir / "scene-01.mp4")
        err = io.StringIO()
        with self.no_path(), contextlib.redirect_stderr(err):
            code = qa_frames.main([str(self.dir), "--clip", "scene-01.mp4"])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue().strip(),
                         "qa_frames: ffmpeg and ffprobe are required and were not found on PATH")


if __name__ == "__main__":
    unittest.main()
