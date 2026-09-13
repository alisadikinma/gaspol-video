import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import _venv, thumb_scrim

HAS_PIL = importlib.util.find_spec("PIL") is not None
HAS_VENV = _venv.venv_python().exists()
ROOT = Path(__file__).resolve().parent.parent.parent


class WcagContrastTest(unittest.TestCase):
    def test_white_on_black_is_21_to_1(self):
        self.assertAlmostEqual(thumb_scrim.wcag_contrast((255, 255, 255), (0, 0, 0)), 21.0, places=1)

    def test_order_of_arguments_does_not_matter(self):
        a = thumb_scrim.wcag_contrast((255, 255, 255), (0, 0, 0))
        b = thumb_scrim.wcag_contrast((0, 0, 0), (255, 255, 255))
        self.assertAlmostEqual(a, b)

    def test_identical_colours_is_1_to_1(self):
        self.assertAlmostEqual(thumb_scrim.wcag_contrast((128, 64, 32), (128, 64, 32)), 1.0, places=3)


class ParseBoxTest(unittest.TestCase):
    def test_valid_box_inside_image(self):
        self.assertEqual(thumb_scrim.parse_box("10,20,100,200", 1280, 720), (10, 20, 100, 200))

    def test_box_extending_past_the_right_edge_is_rejected(self):
        with self.assertRaises(thumb_scrim.ThumbScrimError):
            thumb_scrim.parse_box("10,20,2000,200", 1280, 720)

    def test_box_extending_past_the_bottom_edge_is_rejected(self):
        with self.assertRaises(thumb_scrim.ThumbScrimError):
            thumb_scrim.parse_box("10,20,100,900", 1280, 720)

    def test_negative_origin_is_rejected(self):
        with self.assertRaises(thumb_scrim.ThumbScrimError):
            thumb_scrim.parse_box("-5,20,100,200", 1280, 720)

    def test_malformed_box_string_is_rejected(self):
        with self.assertRaises(thumb_scrim.ThumbScrimError):
            thumb_scrim.parse_box("not,a,box", 1280, 720)


@unittest.skipUnless(HAS_PIL, "Pillow not installed on this interpreter")
class ScrimContrastTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image, ImageDraw

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # Green headline text on a grey ground — the scrim must darken the ground enough
        # to reach the requested contrast without touching the protected green letters.
        im = Image.new("RGB", (640, 360), (140, 140, 140))
        draw = ImageDraw.Draw(im)
        draw.rectangle([40, 40, 400, 160], fill=(60, 200, 60))
        self.path = self.dir / "src.png"
        im.save(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_target_contrast_is_reached(self):
        from PIL import Image

        im = Image.open(self.path)
        # fade_y/x_hold/x_fade cover the whole box at full strength, so the ground
        # darkens uniformly and the search has real room to move.
        out_im, strength, contrast = thumb_scrim.fit_to_target_contrast(
            im, (0, 0, 640, 200), target_contrast=4.0, hue=120.0,
            fade_y=300, x_hold=640, x_fade=640,
        )
        self.assertGreaterEqual(contrast, 4.0)
        self.assertLessEqual(strength, 0.95)
        self.assertEqual(out_im.size, (640, 360))

    def test_cli_writes_output_with_target_contrast(self):
        out_path = self.dir / "out.png"
        rc = thumb_scrim.main([
            "--in", str(self.path), "--out", str(out_path),
            "--target-contrast", "4.0", "--text-box", "0,0,640,200",
            "--fade-y", "300", "--x-hold", "640", "--x-fade", "640",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out_path.exists())

    def test_plain_scrim_darkens_the_top_of_the_image(self):
        from PIL import Image

        im = Image.open(self.path)
        out = thumb_scrim.apply_scrim(im, strength=0.6, fade_y=300, x_hold=0, x_fade=640)
        top_before = im.convert("RGB").getpixel((500, 10))
        top_after = out.getpixel((500, 10))
        self.assertLess(sum(top_after), sum(top_before))

    def test_missing_input_is_a_clear_error_not_a_traceback(self):
        rc = thumb_scrim.main([
            "--in", str(self.dir / "does-not-exist.png"), "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(rc, 1)

    def test_unreadable_input_is_a_clear_error(self):
        bad = self.dir / "not-an-image.png"
        bad.write_bytes(b"this is not a png file, just text pretending to be one")
        rc = thumb_scrim.main(["--in", str(bad), "--out", str(self.dir / "out.png")])
        self.assertEqual(rc, 1)

    def test_jpg_below_youtube_minimum_is_refused(self):
        # self.path is 640x360, well under the 1280x720 YouTube minimum.
        rc = thumb_scrim.main([
            "--in", str(self.path), "--out", str(self.dir / "out.png"), "--jpg",
        ])
        self.assertEqual(rc, 1)
        self.assertFalse((self.dir / "out.jpg").exists())

    def test_jpg_at_or_above_youtube_minimum_is_allowed(self):
        from PIL import Image

        big_path = self.dir / "big.png"
        Image.new("RGB", (1280, 720), (50, 50, 50)).save(big_path)
        rc = thumb_scrim.main([
            "--in", str(big_path), "--out", str(self.dir / "out.png"), "--jpg",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((self.dir / "out.jpg").exists())


@unittest.skipUnless(HAS_PIL, "Pillow not installed on this interpreter")
class CompositeLogoTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        base = Image.new("RGB", (400, 400), (10, 10, 10))
        self.base_path = self.dir / "base.png"
        base.save(self.base_path)

        # A small solid-colour RGBA logo — a real alpha channel, no keying needed.
        logo = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for y in range(100):
            for x in range(100):
                logo.putpixel((x, y), (200, 60, 30, 255))
        self.logo_path = self.dir / "logo.png"
        logo.save(self.logo_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_logo_lands_at_the_requested_centre(self):
        from tools import composite_logo

        out_path = self.dir / "out.png"
        composite_logo.composite_logo(
            str(self.base_path), str(self.logo_path), str(out_path),
            center=(200, 200), size=100, glow=None,
        )
        from PIL import Image
        out = Image.open(out_path).convert("RGB")
        self.assertEqual(out.getpixel((200, 200)), (200, 60, 30))

    def test_clear_box_is_painted_with_bg(self):
        from tools import composite_logo

        out_path = self.dir / "out.png"
        composite_logo.composite_logo(
            str(self.base_path), str(self.logo_path), str(out_path),
            clear_box="0,0,100,100", bg=(9, 9, 9), feather=0,
            center=(200, 200), size=50, glow=None,
        )
        from PIL import Image
        out = Image.open(out_path).convert("RGB")
        corner = out.getpixel((5, 5))
        for channel in corner:
            self.assertLess(abs(channel - 9), 3)

    def test_jpg_output_is_under_2mb(self):
        from tools import composite_logo

        out_path = self.dir / "out.png"
        composite_logo.composite_logo(
            str(self.base_path), str(self.logo_path), str(out_path),
            center=(200, 200), size=100, glow=None, jpg=True,
        )
        jpg_path = out_path.with_suffix(".jpg")
        self.assertTrue(jpg_path.exists())
        self.assertLessEqual(jpg_path.stat().st_size, 2 * 1024 * 1024)

    def test_wide_logo_keeps_its_aspect_ratio(self):
        from PIL import Image
        from tools import composite_logo

        wide = Image.new("RGBA", (400, 100), (0, 0, 0, 0))
        for y in range(100):
            for x in range(400):
                wide.putpixel((x, y), (200, 60, 30, 255))
        wide_path = self.dir / "wide-logo.png"
        wide.save(wide_path)

        rgb, alpha, warn = composite_logo.load_logo_layer(str(wide_path), 400)
        self.assertEqual(rgb.size, alpha.size)
        w, h = rgb.size
        self.assertAlmostEqual(w / h, 4.0, delta=0.05)
        self.assertEqual(w, 400, "the longest side must land exactly on the requested size")

    def test_palette_png_with_transparency_keeps_transparent_background_transparent(self):
        from PIL import Image
        from tools import composite_logo

        # A "P" mode image with a tRNS entry — a real logo exported as an indexed PNG.
        # Index 0 is fully transparent (and palette-mapped to black, the exact colour a
        # white-background colour-distance keying would misread as "solid ink"); index 1
        # is the opaque mark colour. The mark is a RING (10..90 opaque, a 40..60 hole back
        # to index 0) so the transparent hole survives the alpha bbox crop and still sits
        # inside the returned layer — a corner-only fixture would just get cropped away.
        pal = Image.new("P", (100, 100), 0)
        pal.putpalette([0, 0, 0] + [200, 60, 30] + [0, 0, 0] * 254)
        pal.info["transparency"] = 0
        for y in range(100):
            for x in range(100):
                in_outer = 10 <= x < 90 and 10 <= y < 90
                in_hole = 40 <= x < 60 and 40 <= y < 60
                pal.putpixel((x, y), 1 if (in_outer and not in_hole) else 0)
        pal_path = self.dir / "palette-logo.png"
        pal.save(pal_path)

        rgb, alpha, warn = composite_logo.load_logo_layer(str(pal_path), 100)
        # The bbox-cropped layer is 80x80 (10..90); its centre (40,40) is the hole and
        # must read transparent — proof the real alpha channel was used (P converted to
        # RGBA), not white-background colour-distance keying (which would see the hole's
        # black palette colour as solid ink and report it opaque).
        self.assertEqual(alpha.getpixel((alpha.width // 2, alpha.height // 2)), 0)

    def test_no_claude_default_colours_survive(self):
        from tools import composite_logo

        source = Path(composite_logo.__file__).read_text()
        self.assertNotIn("247,130,74", source)
        self.assertNotIn("217,119,87", source)
        self.assertNotIn("--tile", source)

    def test_missing_base_is_a_clear_error_not_a_traceback(self):
        from tools import composite_logo

        rc = composite_logo.main([
            "--base", str(self.dir / "does-not-exist.png"), "--logo", str(self.logo_path),
            "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(rc, 1)

    def test_missing_logo_is_a_clear_error(self):
        from tools import composite_logo

        rc = composite_logo.main([
            "--base", str(self.base_path), "--logo", str(self.dir / "does-not-exist.png"),
            "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(rc, 1)

    def test_unreadable_base_is_a_clear_error(self):
        from tools import composite_logo

        bad = self.dir / "not-an-image.png"
        bad.write_bytes(b"definitely not a png")
        rc = composite_logo.main([
            "--base", str(bad), "--logo", str(self.logo_path), "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(rc, 1)

    def test_jpg_below_youtube_minimum_is_refused(self):
        from tools import composite_logo

        # self.base_path is 400x400, well under the 1280x720 YouTube minimum.
        rc = composite_logo.main([
            "--base", str(self.base_path), "--logo", str(self.logo_path),
            "--out", str(self.dir / "out.png"), "--jpg",
        ])
        self.assertEqual(rc, 1)
        self.assertFalse((self.dir / "out.jpg").exists())

    def test_jpg_at_or_above_youtube_minimum_is_allowed(self):
        from PIL import Image
        from tools import composite_logo

        big_path = self.dir / "big-base.png"
        Image.new("RGB", (1280, 720), (10, 10, 10)).save(big_path)
        rc = composite_logo.main([
            "--base", str(big_path), "--logo", str(self.logo_path),
            "--out", str(self.dir / "out.png"), "--jpg",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((self.dir / "out.jpg").exists())


@unittest.skipUnless(HAS_VENV, "no dedicated venv (tools/setup.sh) on this machine")
class StdlibSafeMissingFileTest(unittest.TestCase):
    """These tests never import PIL themselves — they shell out to the CLI under the bare
    `python3` on PATH, relying on `tools/_venv.py`'s own re-exec into the dedicated venv (the
    same thing a real invocation does), so the missing-file path is exercised without this
    test file needing Pillow at all."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, script, args):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / script)] + args,
            capture_output=True, text=True,
        )

    def test_thumb_scrim_missing_input(self):
        proc = self._run("thumb_scrim.py", [
            "--in", str(self.dir / "nope.png"), "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("thumb_scrim:", proc.stderr)

    def test_composite_logo_missing_base(self):
        proc = self._run("composite_logo.py", [
            "--base", str(self.dir / "nope.png"), "--logo", str(self.dir / "nope2.png"),
            "--out", str(self.dir / "out.png"),
        ])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("composite_logo:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
