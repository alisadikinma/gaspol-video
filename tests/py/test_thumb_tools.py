import importlib.util
import tempfile
import unittest
from pathlib import Path

from tools import thumb_scrim

HAS_PIL = importlib.util.find_spec("PIL") is not None


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

    def test_no_claude_default_colours_survive(self):
        from tools import composite_logo

        source = Path(composite_logo.__file__).read_text()
        self.assertNotIn("247,130,74", source)
        self.assertNotIn("217,119,87", source)
        self.assertNotIn("--tile", source)


if __name__ == "__main__":
    unittest.main()
