import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.py import media
from tools import person_mask

HAS_PIL = importlib.util.find_spec("PIL") is not None
needs_pil = unittest.skipUnless(HAS_PIL, "Pillow not importable on this interpreter")

W, H = 32, 24


def _segmenter(miss=(), counter=None, tiny=()):
    """Fake segmenter: returns None on indices in `miss`, a near-empty mask on `tiny`."""
    from PIL import Image

    def segment(rgb, index, w, h):
        if counter is not None:
            counter.append(index)
        if index in miss:
            return None
        img = Image.new("L", (w, h), 0)
        if index in tiny:
            img.paste(255, (0, 0, 1, 1))  # 1 px of 768, well under 0.5%
        else:
            img.paste(255, (8, 4, 24, 20))
        return img
    return segment


def _frames(n, w=W, h=H):
    return iter([bytes(w * h * 3)] * n)


@needs_pil
class BuildAndDecideTest(unittest.TestCase):
    def test_refuses_when_more_than_ten_percent_miss(self):
        masks, miss = person_mask.build_masks(_frames(10), _segmenter(miss={0, 1}), W, H, 0)
        self.assertEqual(miss, [1, 2])
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.decide(miss, len(masks), 0.10)
        self.assertIn("20%", str(ctx.exception))
        self.assertIn("1, 2", str(ctx.exception))

    def test_zero_frames_refused(self):
        masks, miss = person_mask.build_masks(iter([]), _segmenter(), W, H, 0)
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.decide(miss, len(masks), 0.10)
        self.assertIn("clip has no frames", str(ctx.exception))

    def test_single_frame_with_person_ok(self):
        masks, miss = person_mask.build_masks(_frames(1), _segmenter(), W, H, 0)
        person_mask.decide(miss, len(masks), 0.10)
        self.assertEqual((len(masks), miss), (1, []))

    def test_exactly_ten_percent_passes_eleven_fails(self):
        masks, miss = person_mask.build_masks(_frames(10), _segmenter(miss={4}), W, H, 0)
        person_mask.decide(miss, 10, 0.10)
        masks, miss = person_mask.build_masks(_frames(100), _segmenter(miss=set(range(11))), W, H, 0)
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.decide(miss, 100, 0.10)
        self.assertIn("11%", str(ctx.exception))
        masks, miss = person_mask.build_masks(_frames(100), _segmenter(miss=set(range(10))), W, H, 0)
        person_mask.decide(miss, 100, 0.10)

    def test_message_lists_only_first_twenty_frames(self):
        miss = list(range(1, 31))
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.decide(miss, 30, 0.10)
        msg = str(ctx.exception)
        self.assertIn("20", msg)
        self.assertNotIn("21,", msg)

    def test_tiny_area_counts_as_miss_and_mask_is_black(self):
        masks, miss = person_mask.build_masks(_frames(3), _segmenter(tiny={1}), W, H, 0)
        self.assertEqual(miss, [2])
        self.assertEqual(len(masks), 3)
        self.assertEqual(masks[1].getextrema(), (0, 0))

    def test_missed_frame_still_gets_black_mask(self):
        masks, miss = person_mask.build_masks(_frames(2), _segmenter(miss={0}), W, H, 0)
        self.assertEqual(len(masks), 2)
        self.assertEqual(masks[0].getextrema(), (0, 0))
        self.assertEqual(masks[1].getextrema(), (0, 255))

    def test_feather_softens_edges(self):
        hard, _ = person_mask.build_masks(_frames(1), _segmenter(), W, H, 0)
        soft, _ = person_mask.build_masks(_frames(1), _segmenter(), W, H, 3)
        self.assertGreater(len(soft[0].getcolors()), len(hard[0].getcolors()))


class ProbeTest(unittest.TestCase):
    @media.requires_ffmpeg
    def test_probe_and_read_frames(self):
        with tempfile.TemporaryDirectory() as d:
            clip = media.make_silent_clip(Path(d) / "c.mp4", seconds=1, fps=10, size="64x48")
            w, h, fps, frames = person_mask.probe(clip)
            self.assertEqual((w, h, frames), (64, 48, 10))
            self.assertAlmostEqual(fps, 10.0)
            got = list(person_mask.read_frames(clip, w, h))
            self.assertEqual(len(got), 10)
            self.assertEqual(len(got[0]), 64 * 48 * 3)


@needs_pil
@media.requires_ffmpeg
class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "proj"
        self.out.mkdir()
        self.clip = media.make_silent_clip(Path(self.tmp.name) / "c.mp4", seconds=1, fps=10, size="64x48")
        self.mask_dir = self.out / ".tmp" / "mask-03"

    def go(self, segment=None, **kw):
        kw.setdefault("model_sha", "m1")
        return person_mask.run(str(self.out), "03", self.clip, segment or _segmenter(), **kw)

    def test_writes_numbered_pngs_and_stamp(self):
        res = self.go()
        names = sorted(p.name for p in self.mask_dir.glob("*.png"))
        self.assertEqual(names, [f"{i:05d}.png" for i in range(1, 11)])
        self.assertEqual(res["frames"], 10)
        self.assertEqual(res["miss"], 0)
        self.assertFalse(res["cached"])
        self.assertTrue((self.mask_dir / "source.json").exists())

    def test_cache_hit_does_not_call_segment(self):
        self.go()
        calls = []
        res = self.go(_segmenter(counter=calls))
        self.assertEqual(calls, [])
        self.assertTrue(res["cached"])

    def test_cache_miss_on_changed_clip_bytes(self):
        self.go()
        with open(self.clip, "ab") as f:
            f.write(b"\0")
        calls = []
        self.go(_segmenter(counter=calls))
        self.assertTrue(calls)

    def test_cache_miss_on_changed_feather(self):
        self.go(feather_px=4)
        calls = []
        self.go(_segmenter(counter=calls), feather_px=2)
        self.assertTrue(calls)

    def test_cache_miss_on_changed_model(self):
        self.go()
        calls = []
        self.go(_segmenter(counter=calls), model_sha="m2")
        self.assertTrue(calls)

    def test_cache_miss_on_missing_png(self):
        self.go()
        (self.mask_dir / "00005.png").unlink()
        calls = []
        self.go(_segmenter(counter=calls))
        self.assertTrue(calls)
        self.assertTrue((self.mask_dir / "00005.png").exists())

    def test_force_reruns(self):
        self.go()
        calls = []
        res = self.go(_segmenter(counter=calls), force=True)
        self.assertTrue(calls)
        self.assertFalse(res["cached"])

    def test_refused_run_writes_nothing(self):
        with self.assertRaises(person_mask.MaskRefused):
            self.go(_segmenter(miss=set(range(5))))
        self.assertFalse(self.mask_dir.exists())

    def test_stamp_written_last(self):
        from PIL import Image
        real_save = Image.Image.save
        count = []

        def flaky(self_img, *a, **k):
            count.append(1)
            if len(count) == 4:
                raise OSError("disk full")
            return real_save(self_img, *a, **k)

        with mock.patch.object(Image.Image, "save", flaky):
            with self.assertRaises(OSError):
                self.go()
        self.assertFalse((self.mask_dir / "source.json").exists())
        self.assertFalse(person_mask.cache_valid(
            self.mask_dir, person_mask.clip_sha256(self.clip), "m1", 4))

    def test_stale_pngs_removed_when_frame_count_shrinks(self):
        self.go()
        short = media.make_silent_clip(Path(self.tmp.name) / "s.mp4", seconds=1, fps=5, size="64x48")
        person_mask.run(str(self.out), "03", short, _segmenter(), model_sha="m1")
        names = sorted(p.name for p in self.mask_dir.glob("*.png"))
        self.assertEqual(names, [f"{i:05d}.png" for i in range(1, 6)])

    def test_missing_output_folder_refused(self):
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.run(str(self.out / "nope"), "03", self.clip, _segmenter(), model_sha="m1")
        self.assertIn("does not exist", str(ctx.exception))

    def test_clip_without_frames_refused(self):
        empty = Path(self.tmp.name) / "empty.mp4"
        empty.write_bytes(b"")
        with self.assertRaises(person_mask.MaskRefused) as ctx:
            person_mask.run(str(self.out), "03", str(empty), _segmenter(), model_sha="m1")
        self.assertIn("clip has no frames", str(ctx.exception))


class CacheValidTest(unittest.TestCase):
    def test_no_stamp_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(person_mask.cache_valid(Path(d), "a", "b", 4))

    def test_missing_dir_is_invalid(self):
        self.assertFalse(person_mask.cache_valid(Path("/nonexistent-xyz"), "a", "b", 4))


class CliTest(unittest.TestCase):
    def test_missing_output_folder_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["python3", "tools/person_mask.py", str(Path(d) / "nope"), "01", "x.mp4"],
                capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("does not exist", proc.stderr)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "speaker-2s.mp4"
HAS_MODEL = person_mask.model_path().is_file() and (
    Path.home() / ".gaspol-video" / "venv" / "bin" / "python").exists()


@unittest.skipUnless(HAS_MODEL and media.FFMPEG, "venv mediapipe model or ffmpeg not installed")
class RealModelTest(unittest.TestCase):
    # tests/fixtures/speaker-2s.mp4 = 2 s of a presenter-to-camera clip (Ali, the repo owner), 360 px.
    def test_real_model_on_reference_clip(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["python3", "tools/person_mask.py", d, "25", str(FIXTURE)],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            stamp = (Path(d) / ".tmp" / "mask-25" / "source.json").read_text()
        m = re.search(r"mask 25: (\d+) frames, (\d+) without person", proc.stdout)
        self.assertIsNotNone(m, proc.stdout)
        frames, misses = int(m.group(1)), int(m.group(2))
        self.assertGreater(frames, 0, stamp)
        self.assertGreaterEqual((frames - misses) / frames, 0.95, proc.stdout)


if __name__ == "__main__":
    unittest.main()
