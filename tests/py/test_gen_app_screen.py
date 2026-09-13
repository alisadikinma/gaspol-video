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


class IsPlaceholderBrandTest(unittest.TestCase):
    TEMPLATE = {
        "_comment": "placeholder",
        "background": "#0b1f2a",
        "ink": "#f2f6f7",
        "inkSoft": "#9fb4bd",
        "accent": "#5fd0c4",
        "displayFont": "Inter, system-ui, sans-serif",
        "bodyFont": "Inter, system-ui, sans-serif",
    }

    def test_template_values_are_placeholder(self):
        from tools.gen_app_screen import is_placeholder_brand

        self.assertTrue(is_placeholder_brand(dict(self.TEMPLATE), self.TEMPLATE))

    def test_changed_accent_is_not_placeholder(self):
        from tools.gen_app_screen import is_placeholder_brand

        brand = dict(self.TEMPLATE)
        brand["accent"] = "#ff0000"
        self.assertFalse(is_placeholder_brand(brand, self.TEMPLATE))


class MockJobsTest(unittest.TestCase):
    def _project_with_component(self, tmp, component="AnprDashboardScreen"):
        component_dir = Path(tmp) / "shots" / "src" / "shots" / "screens"
        component_dir.mkdir(parents=True, exist_ok=True)
        (component_dir / f"{component}.tsx").write_text("export default function X() {}", encoding="utf-8")
        return tmp

    def test_expands_two_states_into_two_jobs(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            self._project_with_component(tmp)
            spec = [
                {
                    "name": "anpr-dashboard",
                    "component": "AnprDashboardScreen",
                    "states": ["initial", "plate-detected"],
                }
            ]
            data = {"anpr-dashboard": {"gate": "Gerbang 3"}}
            jobs = mock_jobs(spec, data, tmp)
            outs = sorted(job["out"] for job in jobs)
            self.assertEqual(len(jobs), 2)
            self.assertTrue(outs[0].endswith("ref/ui-anpr-dashboard-initial.png"))
            self.assertTrue(outs[1].endswith("ref/ui-anpr-dashboard-plate-detected.png"))

    def test_missing_data_key_raises(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            self._project_with_component(tmp)
            spec = [{"name": "anpr-dashboard", "component": "AnprDashboardScreen", "states": ["initial"]}]
            with self.assertRaises(ScreenError) as ctx:
                mock_jobs(spec, {}, tmp)
            self.assertIn("anpr-dashboard", str(ctx.exception))

    def test_missing_component_file_raises_with_path(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            spec = [{"name": "anpr-dashboard", "component": "AnprDashboardScreen", "states": ["initial"]}]
            data = {"anpr-dashboard": {"gate": "Gerbang 3"}}
            with self.assertRaises(ScreenError) as ctx:
                mock_jobs(spec, data, tmp)
            expected_path = str(Path(tmp) / "shots" / "src" / "shots" / "screens" / "AnprDashboardScreen.tsx")
            self.assertIn(expected_path, str(ctx.exception))

    def test_bad_state_name_rejected(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            self._project_with_component(tmp)
            spec = [{"name": "anpr-dashboard", "component": "AnprDashboardScreen", "states": ["Bad State!"]}]
            data = {"anpr-dashboard": {"gate": "Gerbang 3"}}
            with self.assertRaises(ScreenError):
                mock_jobs(spec, data, tmp)

    def test_only_filters_to_one_screen(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            self._project_with_component(tmp, "AnprDashboardScreen")
            self._project_with_component(tmp, "OtherScreen")
            spec = [
                {"name": "anpr-dashboard", "component": "AnprDashboardScreen", "states": ["initial"]},
                {"name": "other-screen", "component": "OtherScreen", "states": ["initial"]},
            ]
            data = {"anpr-dashboard": {"gate": "Gerbang 3"}, "other-screen": {"x": 1}}
            jobs = mock_jobs(spec, data, tmp, only="anpr-dashboard")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["name"], "anpr-dashboard")


if __name__ == "__main__":
    unittest.main()
