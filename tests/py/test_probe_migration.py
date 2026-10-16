"""check_vo_duration and track_screen read media facts through vidkit.ff only."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import check_vo_duration, track_screen
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


if __name__ == "__main__":
    unittest.main()
