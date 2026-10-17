import json
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


if __name__ == "__main__":
    unittest.main()
