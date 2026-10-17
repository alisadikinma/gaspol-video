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


# ---- GV-23: overlay text measured from a text-only Remotion render -------------------------

def overlay_workspace(tmp, size=(180, 320), cues=None, scene="03"):
    """proj/shots/{src/shots/overlay-<scene>.json, public/overlay/<scene>/clip.mp4}."""
    proj = Path(tmp) / "proj"
    shots = proj / "shots"
    (shots / "src" / "shots").mkdir(parents=True)
    pub = shots / "public" / "overlay" / scene
    pub.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"testsrc=s={size[0]}x{size[1]}:r=10:d=4", "-pix_fmt", "yuv420p",
                    str(pub / "clip.mp4")], check=True)
    plan = {"scene": scene, "fps": 10, "width": size[0], "height": size[1],
            "durationInFrames": 40, "clip": f"overlay/{scene}/clip.mp4", "mask": None,
            "cues": cues or [{"id": "c1", "inF": 5, "keyF": 8, "outF": 30}]}
    (shots / "src" / "shots" / f"overlay-{scene}.json").write_text(json.dumps(plan))
    return proj, shots


def stub_render(boxes, size=(180, 320), calls=None):
    """A stand-in for the Remotion text-only render: one grey still per cue with a white
    rectangle at boxes[cue id], the same grey (128) the real composition uses."""
    def render(shots_dir, plan_path, out_dir):
        plan = json.loads(Path(plan_path).read_text())
        out = []
        for cue in plan["cues"]:
            x0, y0, x1, y1 = boxes[str(cue["id"])]
            png = Path(out_dir) / f"{plan['scene']}-{cue['id']}.png"
            png.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                            f"color=0x808080:s={size[0]}x{size[1]}", "-vf",
                            f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color=white:t=fill",
                            "-frames:v", "1", str(png)], check=True)
            frame = (cue["keyF"] + cue["outF"]) // 2
            out.append({"id": str(cue["id"]), "frame": frame, "inF": cue["inF"],
                        "outF": cue["outF"], "png": str(png)})
            if calls is not None:
                calls.append((str(shots_dir), str(plan_path), cue["id"]))
        return out
    return render


class FindOverlays(unittest.TestCase):
    def test_workspace_dir_project_dir_and_json_file_all_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            plan = shots / "src" / "shots" / "overlay-03.json"
            for target in (shots, proj, plan):
                found_shots, plans = layout_gate.find_overlays(str(target))
                self.assertEqual(Path(found_shots), shots, target)
                self.assertEqual([Path(p) for p in plans], [plan], target)

    def test_nothing_found_is_an_input_error_naming_the_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(layout_gate.InputError) as cm:
                layout_gate.find_overlays(str(Path(tmp) / "nope"))
            self.assertIn("nope", str(cm.exception))
            (Path(tmp) / "empty").mkdir()
            with self.assertRaises(layout_gate.InputError) as cm:
                layout_gate.find_overlays(str(Path(tmp) / "empty"))
            self.assertIn("overlay_plan.py", str(cm.exception))


class RenderOverlayText(unittest.TestCase):
    def test_runs_the_node_script_in_the_workspace(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            plan = shots / "src" / "shots" / "overlay-03.json"
            out = Path(tmp) / "out"
            out.mkdir()
            (shots / "scripts").mkdir()
            (shots / "scripts" / "render-overlay-text.mjs").write_text("")
            frames = [{"id": "c1", "frame": 19, "inF": 5, "outF": 30, "png": str(out / "03-c1.png")}]
            (out / "overlay-03.frames.json").write_text(json.dumps(frames))
            done = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch("subprocess.run", return_value=done) as run:
                got = layout_gate.render_overlay_text(str(shots), str(plan), str(out))
        self.assertEqual(got, frames)
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "node")
        self.assertIn("scripts/render-overlay-text.mjs", argv[1])
        self.assertEqual(run.call_args.kwargs["cwd"], str(shots))

    def test_failure_stops_with_the_reason_and_no_estimate(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            (shots / "scripts").mkdir()
            (shots / "scripts" / "render-overlay-text.mjs").write_text("")
            bad = mock.Mock(returncode=1, stdout="", stderr="render-overlay-text: Cannot find package '@remotion/bundler'")
            with mock.patch("subprocess.run", return_value=bad):
                with self.assertRaises(layout_gate.InputError) as cm:
                    layout_gate.render_overlay_text(str(shots), str(shots / "src/shots/overlay-03.json"), tmp)
        self.assertIn("@remotion/bundler", str(cm.exception))
        self.assertIn("npm install", str(cm.exception))

    def test_script_missing_names_the_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            with self.assertRaises(layout_gate.InputError) as cm:
                layout_gate.render_overlay_text(str(shots), str(shots / "src/shots/overlay-03.json"), tmp)
        self.assertIn("render-overlay-text.mjs", str(cm.exception))

    def test_node_missing_is_an_input_error(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            (shots / "scripts").mkdir()
            (shots / "scripts" / "render-overlay-text.mjs").write_text("")
            with mock.patch("subprocess.run", side_effect=FileNotFoundError("node")):
                with self.assertRaises(layout_gate.InputError) as cm:
                    layout_gate.render_overlay_text(str(shots), str(shots / "src/shots/overlay-03.json"), tmp)
        self.assertIn("node", str(cm.exception))


class OverlayCli(unittest.TestCase):
    def run_gate(self, tmp, box, detect=None, extra=(), **ws):
        proj, shots = overlay_workspace(tmp, **ws)
        calls = []
        code, out, err = run_cli_render(
            ["check", str(proj), "--overlay", str(shots), *extra],
            detect=detect or fake_face(None), render=stub_render({"c1": box}, calls=calls))
        return proj, code, out, err, calls

    def test_text_inside_the_safe_area_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, calls = self.run_gate(tmp, [20, 100, 150, 140])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(calls), 1)

    def test_measured_box_is_in_the_report_with_scene_and_cue(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [2, 100, 150, 140])
            report = (proj / "work" / "layout-report.md").read_text()
        self.assertEqual(code, 1, out)
        self.assertIn("overlay 03/c1", report)
        self.assertIn("left by 9 px", report)  # safe x0 = 11 at 180 wide, box starts at 2
        self.assertIn("[2, 100, 150, 140]", report)

    def test_each_overflowed_edge_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 30, 175, 280])
        self.assertEqual(code, 1)
        for edge in ("top by 15", "right by 13", "bottom by 27"):
            self.assertIn(edge, out)

    def test_text_over_the_face_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 100, 150, 140],
                                                    detect=fake_face([60, 110, 120, 130]))
        self.assertEqual(code, 1, out)
        self.assertIn("overlaps face", out)
        self.assertIn("overlay 03/c1", out)

    def test_text_clear_of_the_face_passes_even_just_below_it(self):
        # unlike a subtitle, overlay text has no chin gap rule: only touching the face fails
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 140, 150, 170],
                                                    detect=fake_face([60, 60, 120, 138]))
        self.assertEqual(code, 0, out)

    def test_face_is_scaled_from_the_clip_to_the_overlay_size(self):
        # clip is 180x320 but the plan says 360x640: a face at [60,110,120,130] in clip pixels
        # is [120,220,240,260] in overlay pixels
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp, size=(180, 320))
            planf = shots / "src" / "shots" / "overlay-03.json"
            plan = json.loads(planf.read_text())
            plan["width"], plan["height"] = 360, 640
            planf.write_text(json.dumps(plan))
            code, out, err = run_cli_render(
                ["check", str(proj), "--overlay", str(shots)], detect=fake_face([60, 110, 120, 130]),
                render=stub_render({"c1": [130, 225, 230, 255]}, size=(360, 640)))
        self.assertEqual(code, 1, out + err)
        self.assertIn("overlaps face", out)

    def test_no_face_in_the_cue_is_skipped_not_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 100, 150, 140], detect=fake_face(None))
        self.assertEqual(code, 0)
        self.assertIn("no face detected", out)
        self.assertIn("overlay 03/c1", out)

    def test_previews_per_scene_and_platform_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 100, 150, 140])
            for platform in ("tiktok", "reels", "shorts"):
                p = proj / ".tmp" / f"layout-overlay-03-{platform}.jpg"
                self.assertTrue(p.is_file() and p.stat().st_size > 0, p)
                self.assertIn(str(p), out)

    def test_text_only_stills_are_kept_and_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 100, 150, 140])
            self.assertTrue((proj / ".tmp" / "overlay-text" / "03-c1.png").is_file())
        self.assertIn("03-c1.png", out)

    def test_cue_that_drew_nothing_is_a_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)

            def blank(shots_dir, plan_path, out_dir):
                png = Path(out_dir) / "03-c1.png"
                png.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                                "color=0x808080:s=180x320", "-frames:v", "1", str(png)], check=True)
                return [{"id": "c1", "frame": 19, "inF": 5, "outF": 30, "png": str(png)}]
            code, out, err = run_cli_render(["check", str(proj), "--overlay", str(shots)],
                                            detect=fake_face(None), render=blank)
        self.assertEqual(code, 0)
        self.assertIn("drew nothing", out)

    def test_overlay_that_is_not_nine_sixteen_is_noted_and_not_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, calls = self.run_gate(tmp, [20, 100, 150, 140], size=(320, 180))
        self.assertEqual(calls, [])
        self.assertIn("not 9:16", out)

    def test_profile_flag_changes_the_safe_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            # y1 = 208 under short-ads (bottom 35 %): a box ending at 230 passes organic, fails ads
            proj, code, out, err, _ = self.run_gate(tmp, [20, 150, 150, 230])
            self.assertEqual(code, 0, out)
        with tempfile.TemporaryDirectory() as tmp:
            proj, code, out, err, _ = self.run_gate(tmp, [20, 150, 150, 230],
                                                    extra=("--profile", "short-ads"))
            self.assertEqual(code, 1, out)

    def test_overlay_alone_is_enough_to_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            code, out, err = run_cli_render(["check", str(proj), "--overlay", str(shots)],
                                            detect=fake_face(None),
                                            render=stub_render({"c1": [20, 100, 150, 140]}))
        self.assertEqual(code, 0, err)

    def test_overlay_path_missing_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            code, out, err = run_cli_render(["check", str(proj), "--overlay", str(Path(tmp) / "gone")],
                                            detect=fake_face(None), render=stub_render({}))
        self.assertEqual(code, 2)
        self.assertIn("gone", err)

    def test_render_failure_exit_2_with_the_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)

            def boom(*a):
                raise layout_gate.InputError("remotion cannot render here: no chrome")
            code, out, err = run_cli_render(["check", str(proj), "--overlay", str(shots)],
                                            detect=fake_face(None), render=boom)
        self.assertEqual(code, 2)
        self.assertIn("no chrome", err)

    def test_overlay_plus_subtitles_checked_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, shots = overlay_workspace(tmp)
            (proj / "subs.ass").write_text(karaoke.build_ass(WORDS, 4.0, profile="short-organic", per_group=2))
            code, out, err = run_cli_render(
                ["check", str(proj), "--ass", "subs.ass", "--overlay", str(shots)],
                detect=fake_face(None), render=stub_render({"c1": [2, 100, 150, 140]}))
            self.assertEqual(code, 1)
            self.assertIn("overlay 03/c1", out)
            self.assertTrue((proj / ".tmp" / "layout-tiktok.jpg").is_file())
            self.assertTrue((proj / ".tmp" / "layout-overlay-03-tiktok.jpg").is_file())


def run_cli_render(argv, detect=None, render=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = layout_gate.main(argv, detect=detect, render=render)
    return code, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
