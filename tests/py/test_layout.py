import json
import tempfile
import unittest
from pathlib import Path

from tools.vidkit import layout


def _write(doc_text):
    d = tempfile.mkdtemp()
    p = Path(d) / "profiles.json"
    p.write_text(doc_text)
    return p


class LayoutTest(unittest.TestCase):
    def test_short_organic_safe_box(self):
        prof = layout.load("short-organic")
        self.assertEqual(layout.safe_box(prof), (65, 269, 972, 1517))

    def test_short_ads_bottom_inherits_rest(self):
        prof = layout.load("short-ads")
        self.assertEqual(layout.safe_box(prof), (65, 269, 972, 1248))
        self.assertEqual(layout.value(prof, "title.max_words"), 5)

    def test_value_dotted_key(self):
        prof = layout.load("short-organic")
        self.assertEqual(layout.value(prof, "subtitle.per_group"), 4)
        self.assertEqual(layout.value(prof, "width"), 1080)

    def test_value_missing_key(self):
        prof = layout.load("short-organic")
        with self.assertRaises(KeyError):
            layout.value(prof, "subtitle.nope")

    def test_unknown_profile_lists_valid_names(self):
        with self.assertRaises(KeyError) as cm:
            layout.load("nope")
        msg = str(cm.exception)
        self.assertIn("short-organic", msg)
        self.assertIn("short-ads", msg)

    def test_shipped_file_is_valid(self):
        doc = json.loads(layout.DEFAULT_PATH.read_text())
        self.assertEqual(layout.validate(doc), [])

    def test_leaf_without_source_is_reported(self):
        doc = {"profiles": {"p": {"width": 100, "height": 100,
               "safe": {"top": {"pct": 0.1}}}}}
        problems = layout.validate(doc)
        self.assertEqual(len(problems), 1)
        self.assertIn("p.safe.top", problems[0])

    def test_bad_source_prefix_is_reported(self):
        doc = {"profiles": {"p": {"safe": {"top": {"pct": 0.1, "source": "guess"}}}}}
        self.assertEqual(len(layout.validate(doc)), 1)

    def test_empty_source_is_reported(self):
        doc = {"profiles": {"p": {"timeline": {"value": 1, "source": ""}}}}
        self.assertEqual(len(layout.validate(doc)), 1)

    def test_inherits_missing_is_reported(self):
        doc = {"profiles": {"p": {"inherits": "ghost"}}}
        problems = layout.validate(doc)
        self.assertEqual(len(problems), 1)
        self.assertIn("ghost", problems[0])

    def test_validate_without_profiles_key(self):
        self.assertEqual(len(layout.validate({})), 1)

    def test_load_inherits_missing_raises(self):
        p = _write(json.dumps({"profiles": {"p": {"inherits": "ghost"}}}))
        with self.assertRaises(KeyError) as cm:
            layout.load("p", path=p)
        self.assertIn("ghost", str(cm.exception))

    def test_inherit_cycle_raises(self):
        p = _write(json.dumps({"profiles": {
            "a": {"inherits": "b"}, "b": {"inherits": "a"}}}))
        with self.assertRaises(ValueError):
            layout.load("a", path=p)

    def test_malformed_json_names_file(self):
        p = _write("{not json")
        with self.assertRaises(ValueError) as cm:
            layout.load("x", path=p)
        self.assertIn("profiles.json", str(cm.exception))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            layout.load("x", path=Path("/nonexistent/profiles.json"))

    def test_safe_box_missing_edge(self):
        with self.assertRaises(KeyError):
            layout.safe_box({"width": 100, "height": 100, "safe": {}})

    def _leaf(self, key):
        node = json.loads(layout.DEFAULT_PATH.read_text())["profiles"]["short-organic"]
        for part in key.split("."):
            node = node[part]
        return node

    def test_subtitle_values_are_measured(self):
        for key in ("subtitle.font_pct", "subtitle.per_group"):
            src = self._leaf(key)["source"]
            self.assertTrue(src.startswith("data:"), key)
            self.assertIn("docs/evals/short-form-layout-measurement.md", src, key)

    def test_title_values_name_the_measurement_that_found_no_title(self):
        for key in ("title.font_pct", "title.center_y_pct"):
            src = self._leaf(key)["source"]
            self.assertTrue(src.startswith("tafsiran:"), key)
            self.assertIn("docs/evals/short-form-layout-measurement.md", src, key)


if __name__ == "__main__":
    unittest.main()
