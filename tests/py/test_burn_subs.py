import tempfile
import unittest
from pathlib import Path

from tools import burn_subs


class BurnSubsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_font_missing_glyphs(self):
        """A font that cannot draw the text renders boxes, and boxes ship silently."""
        with self.assertRaises(burn_subs.StyleError) as ctx:
            burn_subs.check_font_supports("Latin Only", "Halo — 世界",
                                          supported=set("Halo —abcdefghijklmnopqrstuvwxyz "))
        self.assertIn("世", str(ctx.exception))

    def test_accepts_a_font_that_covers_the_text(self):
        burn_subs.check_font_supports("Inter", "Halo dunia",
                                      supported=set("Halo duniabcdefghijklmnopqrstuvwxyz "))

    def test_rejects_indistinguishable_colours(self):
        with self.assertRaises(burn_subs.StyleError):
            burn_subs.check_contrast("#FFFFFF", "#FEFEFE")

    def test_accepts_high_contrast(self):
        ratio = burn_subs.check_contrast("#FFFFFF", "#101010")
        self.assertGreater(ratio, 4.5)

    def test_style_becomes_an_ass_force_style_string(self):
        style = {"font": "Inter", "size_px": 54, "stroke_px": 3, "position": "bottom",
                 "margin_v_pct": 8}
        force = burn_subs.force_style(style, video_height=1080)
        self.assertIn("FontName=Inter", force)
        self.assertIn("Fontsize=54", force)
        self.assertIn("Outline=3", force)
        self.assertIn("MarginV=86", force)   # 8% of 1080

    def test_missing_srt_is_named(self):
        with self.assertRaises(burn_subs.StyleError) as ctx:
            burn_subs.build_command(self.dir / "in.mp4", self.dir / "missing.srt",
                                    self.dir / "out.mp4", {}, video_height=1080)
        self.assertIn("missing.srt", str(ctx.exception))

    def test_command_escapes_the_subtitle_path(self):
        srt = self.dir / "master.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhalo\n")
        cmd = burn_subs.build_command(self.dir / "in.mp4", srt, self.dir / "out.mp4",
                                      {"font": "Inter"}, video_height=1080)
        joined = " ".join(cmd)
        self.assertIn("subtitles=", joined)
        self.assertIn("force_style", joined)


if __name__ == "__main__":
    unittest.main()
