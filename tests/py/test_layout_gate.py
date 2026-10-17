import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import layout_gate
from tools.vidkit import karaoke, layout

WORDS = [("HELLO", 0.0, 0.8), ("WORLD", 0.8, 1.6), ("AGAIN", 2.0, 2.8), ("NOW", 2.8, 3.6)]


def write_ass(tmp, watermark=None):
    path = Path(tmp) / "t.ass"
    path.write_text(karaoke.build_ass(WORDS, 4.0, watermark=watermark, profile="short-organic",
                                      per_group=2))
    return str(path)


class TextBoxesFromAss(unittest.TestCase):
    def test_box_is_centred_and_above_the_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            boxes = layout_gate.text_boxes_from_ass(write_ass(tmp), [0.8])
        self.assertEqual(len(boxes), 1)
        x0, y0, x1, y1 = boxes[0]["box"]
        self.assertLessEqual(abs((x0 + x1) / 2 - 540), 4)
        # baseline_y_pct 0.617 -> 1185; caps sit above the line-box bottom, not below it
        self.assertLessEqual(y1, 1189)
        self.assertGreater(y1, 1100)

    def test_time_without_an_event_gives_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            boxes = layout_gate.text_boxes_from_ass(write_ass(tmp), [1.9])
        self.assertIsNone(boxes[0]["box"])

    def test_default_times_are_event_midpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass = write_ass(tmp)
            times = layout_gate.subtitle_times(Path(ass).read_text())
            boxes = layout_gate.text_boxes_from_ass(ass)
        self.assertEqual(len(times), 2)
        self.assertEqual([b["t"] for b in boxes], times)
        self.assertTrue(all(b["box"] for b in boxes))
        # first event starts at 0.0 and ends near 1.7 (tail), midpoint is inside it
        self.assertTrue(0.0 < times[0] < 1.8)
        self.assertTrue(2.0 < times[1] < 3.8)

    def test_empty_ass_has_no_times_and_no_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass = Path(tmp) / "e.ass"
            ass.write_text(karaoke.build_ass([], 4.0))
            self.assertEqual(layout_gate.subtitle_times(ass.read_text()), [])
            self.assertEqual(layout_gate.text_boxes_from_ass(str(ass)), [])

    def test_watermark_is_left_out_of_subtitle_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass = write_ass(tmp, watermark="ALISADIKIN")
            boxes = layout_gate.text_boxes_from_ass(ass, [0.8])
        self.assertGreater(boxes[0]["box"][1], 1050)


class OutlineInBox(unittest.TestCase):
    def test_box_on_grey_includes_the_black_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            ass = Path(write_ass(tmp))
            size = layout_gate.play_res(ass.read_text())
            lines = layout_gate._only(ass.read_text(), False)
            on_black = layout_gate._render_box(lines, 0.8, size, tmp, background="black")
            on_grey = layout_gate.text_boxes_from_ass(str(ass), [0.8])[0]["box"]
        outline = 6  # Outline 7; the faintest anti-aliased edge px falls under the threshold
        self.assertLessEqual(on_grey[0], on_black[0] - outline)
        self.assertLessEqual(on_grey[1], on_black[1] - outline)
        self.assertGreaterEqual(on_grey[2], on_black[2] + outline)
        self.assertGreaterEqual(on_grey[3], on_black[3] + outline)


class WatermarkBox(unittest.TestCase):
    def test_measured_at_the_centre(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = layout_gate.watermark_box(write_ass(tmp, watermark="ALISADIKIN"))
        x0, y0, x1, y1 = box
        self.assertLessEqual(abs((x0 + x1) / 2 - 540), 4)
        self.assertLessEqual(abs((y0 + y1) / 2 - 960), 25)

    def test_none_without_a_watermark(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(layout_gate.watermark_box(write_ass(tmp)))


class TitleBox(unittest.TestCase):
    def test_reads_the_box_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            thumb = Path(tmp) / "thumb-a.png"
            thumb.write_bytes(b"x")
            Path(str(thumb) + ".box.json").write_text(json.dumps({"box": [10, 20, 30, 40]}))
            self.assertEqual(layout_gate.title_box(str(thumb)), [10, 20, 30, 40])

    def test_missing_box_json_names_vidkit_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            thumb = Path(tmp) / "thumb-a.png"
            thumb.write_bytes(b"x")
            with self.assertRaises(layout_gate.InputError) as cm:
                layout_gate.title_box(str(thumb))
        self.assertIn("vidkit title", str(cm.exception))


class CheckSafe(unittest.TestCase):
    def setUp(self):
        self.prof = layout.load("short-organic")
        self.safe = layout.safe_box(self.prof)

    def test_inside_is_clean(self):
        box = [self.safe[0] + 10, self.safe[1] + 10, self.safe[2] - 10, self.safe[3] - 10]
        self.assertEqual(layout_gate.check_safe([{"what": "subtitle", "t": 1.0, "box": box}], self.prof), [])

    def test_touching_the_end_edge_is_inside(self):
        box = [self.safe[0], self.safe[1], self.safe[2], self.safe[3]]
        self.assertEqual(layout_gate.check_safe([{"what": "title", "t": None, "box": box}], self.prof), [])

    def test_one_pixel_past_bottom(self):
        box = [self.safe[0] + 10, self.safe[1] + 10, self.safe[2] - 10, self.safe[3] + 1]
        found = layout_gate.check_safe([{"what": "subtitle", "t": 2.5, "box": box}], self.prof)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["edge"], "bottom")
        self.assertEqual(found[0]["overflow_px"], 1)
        self.assertEqual(found[0]["what"], "subtitle")
        self.assertEqual(found[0]["t"], 2.5)
        self.assertEqual(found[0]["box"], box)

    def test_one_finding_per_edge(self):
        box = [self.safe[0] - 5, self.safe[1] + 10, self.safe[2] + 7, self.safe[3] - 10]
        edges = {f["edge"]: f["overflow_px"]
                 for f in layout_gate.check_safe([{"what": "watermark", "t": 0, "box": box}], self.prof)}
        self.assertEqual(edges, {"left": 5, "right": 7})

    def test_none_box_is_not_a_finding(self):
        self.assertEqual(layout_gate.check_safe([{"what": "subtitle", "t": 1.9, "box": None}], self.prof), [])


class CheckFace(unittest.TestCase):
    def setUp(self):
        self.prof = layout.load("short-organic")  # chin_gap_pct 0.10 -> 192 px

    def sub(self, box, t=1.0):
        return {"what": "subtitle", "t": t, "box": box}

    def face(self, box, t=1.0, frame=30):
        return {"frame": frame, "t": t, "box": box}

    def test_intersecting_subtitle_is_flagged(self):
        found, skipped = layout_gate.check_face([self.sub([100, 1000, 900, 1100])],
                                                [self.face([300, 800, 700, 1050])], self.prof)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["kind"], "overlaps face")
        self.assertEqual(skipped, [])

    def test_too_close_under_the_chin_is_flagged(self):
        # face bottom 1000, subtitle top 1100 -> gap 100 < 192
        found, _ = layout_gate.check_face([self.sub([100, 1100, 900, 1200])],
                                          [self.face([300, 600, 700, 1000])], self.prof)
        self.assertEqual([f["kind"] for f in found], ["too close under the face"])
        self.assertEqual(found[0]["gap_px"], 100)
        self.assertEqual(found[0]["min_gap_px"], 192)

    def test_far_enough_below_is_clean(self):
        found, _ = layout_gate.check_face([self.sub([100, 1192, 900, 1300])],
                                          [self.face([300, 600, 700, 1000])], self.prof)
        self.assertEqual(found, [])

    def test_subtitle_wholly_above_the_face_is_clean(self):
        found, _ = layout_gate.check_face([self.sub([100, 200, 900, 300])],
                                          [self.face([300, 600, 700, 1000])], self.prof)
        self.assertEqual(found, [])

    def test_frame_without_a_face_is_skipped_not_passed(self):
        found, skipped = layout_gate.check_face([self.sub([100, 1100, 900, 1200], t=2.0)],
                                                [self.face(None, t=2.0, frame=60)], self.prof)
        self.assertEqual(found, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["frame"], 60)

    def test_nearest_face_sample_in_time_is_used(self):
        faces = [self.face([300, 600, 700, 1000], t=0.0, frame=0), self.face(None, t=3.0, frame=90)]
        found, skipped = layout_gate.check_face([self.sub([100, 1100, 900, 1200], t=2.9)], faces, self.prof)
        self.assertEqual(found, [])
        self.assertEqual([s["frame"] for s in skipped], [90])

    def test_height_of_a_scaled_profile_is_used_for_the_gap(self):
        small = {**self.prof, "width": 180, "height": 320}  # gap 32 px
        found, _ = layout_gate.check_face([self.sub([10, 180, 150, 200])],
                                          [self.face([50, 50, 120, 170])], small)
        self.assertEqual([f["kind"] for f in found], ["too close under the face"])
        self.assertEqual(found[0]["min_gap_px"], 32)

    def test_title_over_the_face(self):
        self.assertEqual(len(layout_gate.check_title_face([100, 400, 900, 600], [300, 500, 700, 900])), 1)
        self.assertEqual(layout_gate.check_title_face([100, 400, 900, 600], [300, 700, 700, 900]), [])
        self.assertEqual(layout_gate.check_title_face([100, 400, 900, 600], None), [])


class UiBands(unittest.TestCase):
    def test_tiktok_pixels(self):
        bands = layout_gate.ui_bands("tiktok", 1080, 1920)
        self.assertIn((0, 1600, 1080, 1920), bands)
        self.assertIn((960, 0, 1080, 1920), bands)
        self.assertIn((0, 0, 1080, 108), bands)

    def test_reels_percentages(self):
        bands = layout_gate.ui_bands("reels", 1080, 1920)
        self.assertIn((0, 1248, 1080, 1920), bands)
        self.assertIn((0, 0, 1080, 269), bands)
        self.assertIn((0, 0, 65, 1920), bands)
        self.assertIn((1015, 0, 1080, 1920), bands)

    def test_shorts_pixels_scale_with_the_frame(self):
        bands = layout_gate.ui_bands("shorts", 540, 960)
        self.assertIn((0, 760, 540, 960), bands)
        self.assertIn((444, 0, 540, 960), bands)

    def test_every_constant_names_a_source(self):
        for name, spec in layout_gate.PLATFORM_BANDS.items():
            self.assertTrue(spec["source"].startswith(("official:", "third-party:")), name)


def small_video(tmp, size="180x320"):
    path = str(Path(tmp) / "clip.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s={size}:r=10:d=4",
                    "-pix_fmt", "yuv420p", path], check=True)
    return path


def run_cli(argv, detect=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = layout_gate.main(argv, detect=detect)
    return code, out.getvalue(), err.getvalue()


def fake_face(box):
    return lambda rgb, i, w, h: box


class Cli(unittest.TestCase):
    def project(self, tmp, margin_v=None):
        proj = Path(tmp) / "proj"
        proj.mkdir()
        if margin_v is None:
            ass = karaoke.build_ass(WORDS, 4.0, watermark="ALISADIKIN", profile="short-organic", per_group=2)
        else:
            ass = karaoke.build_ass(WORDS, 4.0, font_size=86, margin_v=margin_v, per_group=2)
        (proj / "subs.ass").write_text(ass)
        return proj

    def test_pass_exit_0_writes_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            code, out, _ = run_cli(["check", str(proj), "--ass", "subs.ass"])
            report = (proj / "work" / "layout-report.md").read_text()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)
        self.assertIn("PASS", report)
        self.assertIn("face check skipped", out)

    def test_previews_are_written_to_dot_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            run_cli(["check", str(proj), "--ass", "subs.ass"])
            for name in ("tiktok", "reels", "shorts"):
                jpg = proj / ".tmp" / f"layout-{name}.jpg"
                self.assertTrue(jpg.is_file(), name)
                self.assertEqual(jpg.read_bytes()[:2], b"\xff\xd8")

    def test_subtitles_in_the_ui_band_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp, margin_v=100)
            code, out, _ = run_cli(["check", str(proj), "--ass", "subs.ass"])
            report = (proj / "work" / "layout-report.md").read_text()
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("bottom", report)

    def test_empty_ass_is_a_note_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            proj.mkdir()
            (proj / "subs.ass").write_text(karaoke.build_ass([], 4.0))
            code, out, _ = run_cli(["check", str(proj), "--ass", "subs.ass"])
        self.assertEqual(code, 0)
        self.assertIn("no subtitles found", out)

    def test_face_overlap_exit_1_and_scaled_to_the_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            clip = small_video(tmp)  # 180x320, subtitles drawn at 0.617 of the height = y 197
            code, out, _ = run_cli(["check", str(proj), "--video", clip, "--ass", "subs.ass"],
                                   detect=fake_face([60, 150, 120, 200]))
        self.assertEqual(code, 1, out)
        self.assertIn("overlaps face", out)

    def test_face_far_above_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            clip = small_video(tmp)
            code, out, _ = run_cli(["check", str(proj), "--video", clip, "--ass", "subs.ass"],
                                   detect=fake_face([60, 40, 120, 90]))
        self.assertEqual(code, 0, out)

    def test_skipped_face_frames_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            clip = small_video(tmp)
            code, out, _ = run_cli(["check", str(proj), "--video", clip, "--ass", "subs.ass"],
                                   detect=fake_face(None))
            report = (proj / "work" / "layout-report.md").read_text()
        self.assertEqual(code, 0, out)
        self.assertIn("Skipped face samples (2)", out)
        self.assertIn("face sample(s) skipped", out)
        self.assertIn("no face", report)

    def test_thumbnail_title_over_the_face_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            (proj / "packaging").mkdir()
            thumb = proj / "packaging" / "thumb-a.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=gray:s=180x320",
                            "-frames:v", "1", str(thumb)], check=True)
            Path(str(thumb) + ".box.json").write_text(json.dumps({"box": [30, 100, 150, 140]}))
            code, out, _ = run_cli(["check", str(proj), "--thumb", "packaging/thumb-*.png"],
                                   detect=fake_face([60, 90, 120, 160]))
        self.assertEqual(code, 1, out)
        self.assertIn("title", out)

    def _clean_and_stamped(self, tmp, with_source=True, source_exists=True):
        proj = self.project(tmp)
        (proj / "packaging").mkdir()
        clean = proj / "packaging" / "clean.png"
        thumb = proj / "packaging" / "thumb-a.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=white:s=180x320",
                        "-frames:v", "1", str(clean)], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=180x320",
                        "-frames:v", "1", str(thumb)], check=True)
        doc = {"box": [30, 100, 150, 140]}
        if with_source:
            doc["source"] = str(clean)
        Path(str(thumb) + ".box.json").write_text(json.dumps(doc))
        if with_source and not source_exists:
            clean.unlink()
        return proj

    @staticmethod
    def face_only_in_white(face):
        """A detector that sees the face only in the clean (white) image, not the stamped (black) one."""
        return lambda rgb, i, w, h: face if bytes(rgb[:1].tobytes() if hasattr(rgb, "tobytes") else rgb[:1])[0] > 128 else None

    def test_title_checked_against_face_in_the_clean_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._clean_and_stamped(tmp)
            code, out, _ = run_cli(["check", str(proj), "--thumb", "packaging/thumb-*.png"],
                                   detect=self.face_only_in_white([60, 90, 120, 160]))
        self.assertEqual(code, 1, out)
        self.assertIn("title overlaps face", out)
        self.assertNotIn("face checked on stamped image", out)

    def test_title_clear_of_the_face_in_the_source_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._clean_and_stamped(tmp)
            code, out, _ = run_cli(["check", str(proj), "--thumb", "packaging/thumb-*.png"],
                                   detect=self.face_only_in_white([60, 200, 120, 280]))
        self.assertEqual(code, 0, out)

    def test_missing_source_falls_back_to_stamped_image_with_a_note(self):
        for with_source, exists in ((False, True), (True, False)):
            with tempfile.TemporaryDirectory() as tmp:
                proj = self._clean_and_stamped(tmp, with_source=with_source, source_exists=exists)
                code, out, _ = run_cli(["check", str(proj), "--thumb", "packaging/thumb-*.png"],
                                       detect=self.face_only_in_white([60, 90, 120, 160]))
            self.assertIn("face checked on stamped image; source missing", out)
            self.assertEqual(code, 0, out)

    def test_exit_2_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            wide = small_video(tmp, "320x180")
            (proj / "packaging").mkdir()
            nobox = proj / "packaging" / "thumb-a.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=gray:s=180x320",
                            "-frames:v", "1", str(nobox)], check=True)
            cases = {
                "no project": ["check", str(Path(tmp) / "nope"), "--ass", "subs.ass"],
                "nothing to check": ["check", str(proj)],
                "missing file": ["check", str(proj), "--ass", "gone.ass"],
                "unknown profile": ["check", str(proj), "--ass", "subs.ass", "--profile", "nope"],
                "not 9:16": ["check", str(proj), "--video", wide, "--ass", "subs.ass"],
                "title without box.json": ["check", str(proj), "--thumb", "packaging/thumb-a.png"],
                "no thumb match": ["check", str(proj), "--thumb", "packaging/none-*.png"],
                "bad every": ["check", str(proj), "--ass", "subs.ass", "--every", "0"],
            }
            for name, argv in cases.items():
                code, _, err = run_cli(argv, detect=fake_face(None))
                self.assertEqual(code, 2, f"{name}: {err}")
                self.assertTrue(err.strip(), name)

    def test_missing_model_exit_2(self):
        from tools import face_box
        with tempfile.TemporaryDirectory() as tmp:
            proj = self.project(tmp)
            clip = small_video(tmp)
            from unittest import mock
            with mock.patch.object(face_box, "make_detector", side_effect=face_box.ModelMissing("model missing: x; run tools/setup.sh")):
                code, _, err = run_cli(["check", str(proj), "--video", clip, "--ass", "subs.ass"])
        self.assertEqual(code, 2)
        self.assertIn("setup.sh", err)


if __name__ == "__main__":
    unittest.main()
