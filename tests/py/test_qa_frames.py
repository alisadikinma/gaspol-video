import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.py import media
from tools import qa_frames


class FrameTimesTest(unittest.TestCase):
    def test_five_timestamps_last_is_one_frame_before_the_end(self):
        self.assertEqual(qa_frames.frame_times(8.0, 25), [0.0, 2.0, 4.0, 6.0, 7.96])

    def test_clip_shorter_than_one_frame_is_refused(self):
        with self.assertRaises(ValueError):
            qa_frames.frame_times(0.02, 25)


PROMPTS = """# Video prompts

## Act 1

### Scene 05: The gate

VEO prompt body here.

PLAUSIBILITY:
1. MECHANISM — the barrier arm rises from its base.
2. COUNT — one barrier, one booth.
3. FLOW — the truck enters from the left.

Camera: slow dolly-in.

### Scene 06: The yard

No block in this one.

### Scene 7: Loading

PLAUSIBILITY:
1. MECHANISM — hose attaches to the top hatch.
"""


class FindPlausibilityTest(unittest.TestCase):
    def test_found_block_is_copied_verbatim_through_numbered_lines(self):
        block = qa_frames.find_plausibility(PROMPTS, 5)
        self.assertEqual(block, "PLAUSIBILITY:\n"
                                "1. MECHANISM — the barrier arm rises from its base.\n"
                                "2. COUNT — one barrier, one booth.\n"
                                "3. FLOW — the truck enters from the left.")

    def test_unpadded_heading_matches_scene_number_with_leading_zero(self):
        block = qa_frames.find_plausibility(PROMPTS, 7)
        self.assertIn("hose attaches to the top hatch", block)
        self.assertEqual(qa_frames.find_plausibility(PROMPTS, 5),
                         qa_frames.find_plausibility(PROMPTS.replace("Scene 05", "Scene 5"), 5))

    def test_section_without_block_returns_none(self):
        self.assertIsNone(qa_frames.find_plausibility(PROMPTS, 6))

    def test_block_of_a_later_scene_is_not_borrowed(self):
        self.assertIsNone(qa_frames.find_plausibility(PROMPTS, 6))
        self.assertIsNone(qa_frames.find_plausibility(PROMPTS, 9))
        self.assertIsNone(qa_frames.find_plausibility("", 5))


TIMES = [0.0, 2.0, 4.0, 6.0, 7.96]
BLOCK = "PLAUSIBILITY:\n1. MECHANISM — the arm rises from its base."

EXPECTED_SECTION = """## Scene 05

- clip: clips/scene-05.mp4
- clip_sha256: abc123
- sheet: .tmp/qa-scene-05.jpg — frames at 0.00s, 2.00s, 4.00s, 6.00s, 7.96s

PLAUSIBILITY:
1. MECHANISM — the arm rises from its base.

| # | Question | Verdict |
|---|---|---|
| 1 | MECHANISM | |
| 2 | COUNT | |
| 3 | FLOW | |
| 4 | FACING | |
| 5 | PAIR | |
| 6 | PEOPLE | |
| 7 | OVERLAY SURFACE | |
"""


def section(scene=5, sha="abc123", block=BLOCK):
    return dict(scene=scene, clip="clips/scene-%02d.mp4" % scene, sha=sha,
                sheet=".tmp/qa-scene-%02d.jpg" % scene, times=TIMES, plausibility=block)


class RenderSectionTest(unittest.TestCase):
    def test_exact_markdown_shape(self):
        self.assertEqual(qa_frames.render_section(**section()), EXPECTED_SECTION)

    def test_missing_block_says_so_and_keeps_all_seven_rows(self):
        text = qa_frames.render_section(**section(block=None))
        self.assertIn("PLAUSIBILITY block not found in video-prompts.md — "
                      "judge against the scene description", text)
        self.assertEqual(text.count("\n| "), 8)  # header row + seven questions


class MergeSheetTest(unittest.TestCase):
    def judged(self):
        first = qa_frames.merge_sheet("", [section()])
        return first.replace("| 1 | MECHANISM | |", "| 1 | MECHANISM | PASS |") \
                    .replace("| 3 | FLOW | |", "| 3 | FLOW | FAIL: truck reverses |")

    def test_new_sheet_contains_the_section(self):
        self.assertIn(EXPECTED_SECTION, qa_frames.merge_sheet("", [section()]))

    def test_unchanged_hash_keeps_verdicts(self):
        merged = qa_frames.merge_sheet(self.judged(), [section()])
        self.assertIn("| 1 | MECHANISM | PASS |", merged)
        self.assertIn("| 3 | FLOW | FAIL: truck reverses |", merged)
        self.assertNotIn("clip changed since last judged", merged)

    def test_changed_hash_clears_verdicts_and_adds_note(self):
        merged = qa_frames.merge_sheet(self.judged(), [section(sha="def456")])
        self.assertIn("- clip_sha256: def456", merged)
        self.assertIn("- note: clip changed since last judged — verdicts cleared", merged)
        self.assertIn("| 1 | MECHANISM | |", merged)
        self.assertNotIn("| PASS |", merged)
        self.assertNotIn("FAIL: truck reverses", merged)

    def test_other_scenes_are_kept_and_sections_sorted_by_scene(self):
        existing = qa_frames.merge_sheet("", [section(scene=7)])
        merged = qa_frames.merge_sheet(existing, [section(scene=5)])
        self.assertLess(merged.index("## Scene 05"), merged.index("## Scene 07"))
        self.assertEqual(merged.count("## Scene 07"), 1)


def run_main(argv):
    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        code = qa_frames.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_ledger(project, entries):
    (Path(project) / "renders.json").write_text(json.dumps({"renders": entries}), encoding="utf-8")


def ledger_entry(scene, file, phase="5", status="done"):
    return {"file": file, "phase": phase, "scene": scene, "model": "veo-3.1-fast",
            "prompt_sha256": "x", "refs": [], "status": status}


@media.requires_ffmpeg
class MainExtractionTest(unittest.TestCase):
    def test_writes_sheet_and_verdict_section_and_removes_single_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "clips").mkdir()
            media.make_clip(project / "clips" / "scene-01.mp4", seconds=4.0, fps=25)
            write_ledger(project, [ledger_entry(1, "clips/scene-01.mp4")])
            (project / "video-prompts.md").write_text(
                "### Scene 1: Gate\n\nPLAUSIBILITY:\n1. MECHANISM — arm rises.\n", encoding="utf-8")

            code, out, err = run_main([str(project)])

            self.assertEqual(code, 0, err)
            sheet = project / ".tmp" / "qa-scene-01.jpg"
            self.assertTrue(sheet.exists())
            probe = subprocess.run(
                [media.FFPROBE, "-v", "error", "-show_entries", "stream=width",
                 "-of", "csv=p=0", str(sheet)], capture_output=True, text=True)
            self.assertEqual(probe.stdout.strip(), "2400")
            self.assertEqual(sorted(p.name for p in (project / ".tmp").iterdir()),
                             ["qa-scene-01.jpg"])
            text = (project / "work" / "visual-qa.md").read_text(encoding="utf-8")
            self.assertIn("## Scene 01", text)
            self.assertIn("1. MECHANISM — arm rises.", text)
            self.assertRegex(text, r"clip_sha256: [0-9a-f]{64}")
            self.assertIn("scene 01", out)
            self.assertIn("sheet .tmp/qa-scene-01.jpg", out)

    def test_ledger_clip_missing_on_disk_is_skipped_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "clips").mkdir()
            media.make_clip(project / "clips" / "scene-02.mp4", seconds=2.0, fps=25)
            write_ledger(project, [ledger_entry(1, "clips/scene-01.mp4"),
                                   ledger_entry(2, "clips/scene-02.mp4")])
            code, out, err = run_main([str(project)])
            self.assertEqual(code, 0, err)
            self.assertIn("scene 01", out + err)
            self.assertIn("missing", out + err)
            self.assertTrue((project / ".tmp" / "qa-scene-02.jpg").exists())
            self.assertFalse((project / ".tmp" / "qa-scene-01.jpg").exists())

    def test_clip_flag_wins_over_ledger_and_scenes_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "clips").mkdir()
            media.make_clip(project / "clips" / "scene-03.mp4", seconds=2.0, fps=25)
            media.make_clip(project / "clips" / "scene-04.mp4", seconds=2.0, fps=25)
            write_ledger(project, [ledger_entry(3, "clips/scene-03.mp4")])
            code, out, err = run_main([str(project), "--clip", "clips/scene-04.mp4",
                                       "--scenes", "4"])
            self.assertEqual(code, 0, err)
            self.assertTrue((project / ".tmp" / "qa-scene-04.jpg").exists())
            self.assertFalse((project / ".tmp" / "qa-scene-03.jpg").exists())


class ExitTwoTest(unittest.TestCase):
    def test_no_rendered_clips_exits_2_with_the_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_ledger(tmp, [ledger_entry(1, "keyframes/scene-01-start.png", phase="4B")])
            code, out, err = run_main([tmp])
            self.assertEqual(code, 2)
            self.assertIn("qa_frames: no rendered clips found (renders.json has no done phase-5 "
                          "entry; pass --clip for hand-rendered clips)", err)

    def test_unreadable_ledger_exits_2_with_its_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "renders.json").write_text("{not json", encoding="utf-8")
            code, out, err = run_main([tmp])
            self.assertEqual(code, 2)
            self.assertIn("invalid JSON", err)

    def test_clip_without_scene_number_is_refused_with_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "clips").mkdir()
            (Path(tmp) / "clips" / "intro.mp4").write_bytes(b"x")
            code, out, err = run_main([tmp, "--clip", "clips/intro.mp4"])
            self.assertEqual(code, 2)
            self.assertIn("no scene number", err)


if __name__ == "__main__":
    unittest.main()
