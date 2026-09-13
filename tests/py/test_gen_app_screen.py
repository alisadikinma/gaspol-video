import json
import tempfile
import unittest
from pathlib import Path

from tools.gen_app_screen import ScreenError, merge_manifest, shot_path, validate_steps


class ValidateStepsTest(unittest.TestCase):
    def test_unknown_key_rejected(self):
        with self.assertRaises(ScreenError) as ctx:
            validate_steps([{"eval": "x"}])
        self.assertIn("unknown step", str(ctx.exception))

    def test_credential_looking_selector_rejected(self):
        with self.assertRaises(ScreenError) as ctx:
            validate_steps([{"fill": ["#password", "hunter2"]}])
        self.assertIn("credentials", str(ctx.exception))

    def test_credential_looking_value_key_rejected(self):
        with self.assertRaises(ScreenError) as ctx:
            validate_steps([{"fill": ["#api-token", "abc123"]}])
        self.assertIn("credentials", str(ctx.exception))

    def test_bad_shot_name_rejected(self):
        with self.assertRaises(ScreenError):
            validate_steps([{"shot": "Bad Name!"}])

    def test_duplicate_shot_name_rejected(self):
        with self.assertRaises(ScreenError):
            validate_steps([{"shot": "dup"}, {"shot": "dup"}])

    def test_valid_spec_returns_normalised_steps(self):
        steps = [
            {"goto": "/"},
            {"wait": 800},
            {"wait_for": "css=.report-table"},
            {"click": "text=Export PDF", "optional": True, "timeout": 4000},
            {"fill": ["#search", "B 1234 XYZ"]},
            {"press": "Enter"},
            {"scroll": 400},
            {"shot": "anpr-dashboard-initial", "url_label": "app.example.com/dashboard", "title": "Dashboard"},
        ]
        normalised = validate_steps(steps)
        self.assertEqual(len(normalised), len(steps))
        self.assertEqual(normalised[0]["goto"], "/")
        self.assertEqual(normalised[-1]["shot"], "anpr-dashboard-initial")


class ShotPathTest(unittest.TestCase):
    def test_shot_path_lands_in_ref(self):
        path = shot_path("/tmp/project", "anpr-dashboard-initial")
        self.assertEqual(str(path), "/tmp/project/ref/ui-anpr-dashboard-initial.png")


class MergeManifestTest(unittest.TestCase):
    def test_keeps_mock_entries_and_replaces_same_name_capture_entry(self):
        existing = [
            {"name": "mock-screen", "source": "mock", "simulated": True},
            {"name": "cap-screen", "source": "capture", "simulated": False, "file": "ui-cap-screen.png"},
        ]
        new_entries = [
            {"name": "cap-screen", "source": "capture", "simulated": False, "file": "ui-cap-screen-v2.png"},
        ]
        merged = merge_manifest(existing, new_entries)
        by_name = {e["name"]: e for e in merged}
        self.assertEqual(len(merged), 2)
        self.assertEqual(by_name["mock-screen"]["source"], "mock")
        self.assertEqual(by_name["cap-screen"]["file"], "ui-cap-screen-v2.png")

    def test_appends_brand_new_entries(self):
        merged = merge_manifest([], [{"name": "a"}, {"name": "b"}])
        self.assertEqual([e["name"] for e in merged], ["a", "b"])


class ScreensJsonTest(unittest.TestCase):
    def test_missing_screens_json_names_the_path(self):
        from tools.gen_app_screen import load_screens_json

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ScreenError) as ctx:
                load_screens_json(tmp)
            self.assertIn(str(Path(tmp) / "screens" / "screens.json"), str(ctx.exception))

    def test_missing_capture_block_raises(self):
        from tools.gen_app_screen import capture_spec

        with self.assertRaises(ScreenError) as ctx:
            capture_spec({"viewport": [1920, 1080]})
        self.assertIn("no capture block", str(ctx.exception))

    def test_present_capture_block_returned(self):
        from tools.gen_app_screen import capture_spec

        spec = capture_spec({"capture": {"base_url": "https://x", "steps": []}})
        self.assertEqual(spec["base_url"], "https://x")


if __name__ == "__main__":
    unittest.main()
