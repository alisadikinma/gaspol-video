import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tools.gen_app_screen import ScreenError, merge_manifest, run_steps, shot_path, validate_steps


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

    def test_new_credential_keywords_are_rejected(self):
        for selector in ("#pwd", "#pass", "#pin", "#otp", "#api_key", "#apikey", "#auth"):
            with self.assertRaises(ScreenError, msg=selector):
                validate_steps([{"fill": [selector, "x"]}])

    def test_goto_query_string_with_a_credential_keyword_is_rejected(self):
        with self.assertRaises(ScreenError) as ctx:
            validate_steps([{"goto": "/login?token=abc123"}])
        self.assertIn("credentials", str(ctx.exception))

    def test_goto_without_a_credential_looking_query_is_allowed(self):
        validate_steps([{"goto": "/dashboard?tab=overview"}])

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


class FakePage:
    """A minimal Playwright-Page-alike so the step loop is testable without a real browser."""

    def __init__(self, fail=None):
        self.fail = fail or {}
        self.calls = []

        class _Mouse:
            def wheel(inner_self, x, y):
                self._maybe_fail("scroll")
                self.calls.append(("scroll", y))

        class _Keyboard:
            def press(inner_self, key):
                self._maybe_fail("press")
                self.calls.append(("press", key))

        self.mouse = _Mouse()
        self.keyboard = _Keyboard()

    def _maybe_fail(self, key):
        if key in self.fail:
            raise RuntimeError(self.fail[key])

    def goto(self, url):
        self._maybe_fail("goto")
        self.calls.append(("goto", url))

    def wait_for_timeout(self, ms):
        self._maybe_fail("wait")
        self.calls.append(("wait", ms))

    def wait_for_selector(self, selector, timeout=30000):
        self._maybe_fail("wait_for")
        self.calls.append(("wait_for", selector))

    def click(self, selector, timeout=30000):
        self._maybe_fail("click")
        self.calls.append(("click", selector))

    def fill(self, selector, value):
        self._maybe_fail("fill")
        self.calls.append(("fill", selector, value))

    def screenshot(self, path):
        self._maybe_fail("shot")
        Path(path).write_bytes(b"PNG")
        self.calls.append(("shot", path))


class RunStepsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_goto_failure_is_wrapped_with_step_index_and_key(self):
        page = FakePage(fail={"goto": "net::ERR_CONNECTION_REFUSED"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"goto": "/"}], self.project, "https://example.com")
        self.assertIn("step 00 goto", str(ctx.exception))
        self.assertIn("net::ERR_CONNECTION_REFUSED", str(ctx.exception))

    def test_wait_for_failure_is_wrapped(self):
        page = FakePage(fail={"wait_for": "Timeout 30000ms exceeded"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"wait_for": "#app"}], self.project, "")
        self.assertIn("step 00 wait_for", str(ctx.exception))

    def test_non_optional_click_failure_is_wrapped(self):
        page = FakePage(fail={"click": "element not found"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"click": "#btn"}], self.project, "")
        self.assertIn("step 00 click", str(ctx.exception))
        self.assertIn("element not found", str(ctx.exception))

    def test_optional_click_failure_is_swallowed_not_raised(self):
        page = FakePage(fail={"click": "element not found"})
        entries, shot_count = run_steps(
            page, [{"click": "#btn", "optional": True}], self.project, ""
        )
        self.assertEqual(entries, [])
        self.assertEqual(shot_count, 0)

    def test_fill_failure_is_wrapped(self):
        page = FakePage(fail={"fill": "input not visible"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"fill": ["#name", "hi"]}], self.project, "")
        self.assertIn("step 00 fill", str(ctx.exception))

    def test_press_failure_is_wrapped(self):
        page = FakePage(fail={"press": "keyboard busy"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"press": "Enter"}], self.project, "")
        self.assertIn("step 00 press", str(ctx.exception))

    def test_scroll_failure_is_wrapped(self):
        page = FakePage(fail={"scroll": "no viewport"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"scroll": 400}], self.project, "")
        self.assertIn("step 00 scroll", str(ctx.exception))

    def test_shot_failure_is_wrapped(self):
        page = FakePage(fail={"shot": "disk full"})
        with self.assertRaises(ScreenError) as ctx:
            run_steps(page, [{"shot": "home"}], self.project, "")
        self.assertIn("step 00 shot", str(ctx.exception))
        self.assertIn("disk full", str(ctx.exception))

    def test_printed_goto_line_strips_the_query_string(self):
        page = FakePage()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_steps(page, [{"goto": "https://example.com/page?tab=overview"}],
                     self.project, "https://example.com")
        printed = buf.getvalue()
        self.assertIn("step 00 goto https://example.com/page\n", printed)
        self.assertNotIn("tab=overview", printed)
        # the real navigation still receives the full URL, query string included
        self.assertEqual(page.calls[0], ("goto", "https://example.com/page?tab=overview"))

    def test_successful_run_returns_entries_and_shot_count(self):
        page = FakePage()
        entries, shot_count = run_steps(
            page,
            [{"goto": "/"}, {"wait": 100}, {"shot": "home"}],
            self.project,
            "https://example.com",
        )
        self.assertEqual(shot_count, 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "home")
        self.assertTrue((Path(self.project) / "ref" / "ui-home.png").exists())


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

    def test_rerun_of_multi_state_mock_keeps_every_state(self):
        # Found on a real re-run: keying by name alone kept only the last state.
        states = [
            {"name": "anpr-dashboard", "state": "initial", "source": "mock", "simulated": True,
             "file": "ui-anpr-dashboard-initial.png"},
            {"name": "anpr-dashboard", "state": "plate-detected", "source": "mock", "simulated": True,
             "file": "ui-anpr-dashboard-plate-detected.png"},
        ]
        first = merge_manifest([], states)
        second = merge_manifest(first, [dict(e) for e in states])
        self.assertEqual(sorted(e["state"] for e in second), ["initial", "plate-detected"])

    def test_duplicates_left_by_old_merge_collapse(self):
        dup = {"name": "anpr-dashboard", "state": "plate-detected", "file": "ui-anpr-dashboard-plate-detected.png"}
        merged = merge_manifest([dict(dup), dict(dup)], [dict(dup)])
        self.assertEqual(len(merged), 1)

    def test_appends_brand_new_entries(self):
        merged = merge_manifest([], [{"name": "a"}, {"name": "b"}])
        self.assertEqual([e["name"] for e in merged], ["a", "b"])


class WriteManifestTest(unittest.TestCase):
    def test_corrupt_existing_manifest_raises_naming_the_file(self):
        from tools.gen_app_screen import write_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "screens" / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(ScreenError) as ctx:
                write_manifest(tmp, [{"name": "a"}])
            self.assertIn(str(manifest_path), str(ctx.exception))

    def test_wrong_shaped_existing_manifest_raises_naming_the_file(self):
        from tools.gen_app_screen import write_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "screens" / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps(["not", "the", "right", "shape"]), encoding="utf-8")
            with self.assertRaises(ScreenError) as ctx:
                write_manifest(tmp, [{"name": "a"}])
            self.assertIn(str(manifest_path), str(ctx.exception))

    def test_write_is_atomic_and_leaves_no_tmp_file(self):
        from tools.gen_app_screen import write_manifest

        with tempfile.TemporaryDirectory() as tmp:
            write_manifest(tmp, [{"name": "a"}])
            manifest_path = Path(tmp) / "screens" / "manifest.json"
            self.assertTrue(manifest_path.exists())
            leftover_tmp = list(manifest_path.parent.glob("*.tmp"))
            self.assertEqual(leftover_tmp, [])
            self.assertEqual(json.loads(manifest_path.read_text())["screens"][0]["name"], "a")


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

    def test_missing_name_key_raises_naming_the_key(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            spec = [{"component": "AnprDashboardScreen", "states": ["initial"]}]
            with self.assertRaises(ScreenError) as ctx:
                mock_jobs(spec, {}, tmp)
            self.assertIn("name", str(ctx.exception))

    def test_missing_component_key_raises_naming_the_key(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            spec = [{"name": "anpr-dashboard", "states": ["initial"]}]
            with self.assertRaises(ScreenError) as ctx:
                mock_jobs(spec, {"anpr-dashboard": {}}, tmp)
            self.assertIn("component", str(ctx.exception))

    def test_missing_states_key_raises_naming_the_key(self):
        from tools.gen_app_screen import mock_jobs

        with tempfile.TemporaryDirectory() as tmp:
            self._project_with_component(tmp)
            spec = [{"name": "anpr-dashboard", "component": "AnprDashboardScreen"}]
            with self.assertRaises(ScreenError) as ctx:
                mock_jobs(spec, {"anpr-dashboard": {}}, tmp)
            self.assertIn("states", str(ctx.exception))

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


class RunMockJsonErrorsTest(unittest.TestCase):
    def test_invalid_brand_json_raises_naming_the_file(self):
        from tools.gen_app_screen import run_mock

        with tempfile.TemporaryDirectory() as tmp:
            brand_path = Path(tmp) / "shots" / "src" / "shots" / "brand.json"
            brand_path.parent.mkdir(parents=True)
            brand_path.write_text("{not valid", encoding="utf-8")
            with self.assertRaises(ScreenError) as ctx:
                run_mock(tmp)
            self.assertIn(str(brand_path), str(ctx.exception))

    def test_invalid_data_json_raises_naming_the_file(self):
        from tools.gen_app_screen import TEMPLATE_BRAND_PATH, run_mock

        with tempfile.TemporaryDirectory() as tmp:
            brand_path = Path(tmp) / "shots" / "src" / "shots" / "brand.json"
            brand_path.parent.mkdir(parents=True)
            template = json.loads(TEMPLATE_BRAND_PATH.read_text(encoding="utf-8"))
            template["accent"] = "#ff0000"  # non-placeholder so that gate passes
            brand_path.write_text(json.dumps(template), encoding="utf-8")

            screens_json = Path(tmp) / "screens" / "screens.json"
            screens_json.parent.mkdir(parents=True)
            screens_json.write_text(
                json.dumps({"mock": [{"name": "a", "component": "X", "states": ["initial"]}]}),
                encoding="utf-8",
            )

            data_path = Path(tmp) / "screens" / "data.json"
            data_path.write_text("{not valid", encoding="utf-8")

            with self.assertRaises(ScreenError) as ctx:
                run_mock(tmp)
            self.assertIn(str(data_path), str(ctx.exception))


class RunCaptureBrowserLaunchTest(unittest.TestCase):
    def test_missing_chromium_executable_is_a_clear_screen_error(self):
        from tools import gen_app_screen

        class FakePlaywrightError(Exception):
            pass

        class FakeChromium:
            def launch(self, headless=True):
                raise FakePlaywrightError(
                    "Executable doesn't exist at /fake/path/chromium\n"
                    "Looks like Playwright was just installed or updated."
                )

        class FakeP:
            chromium = FakeChromium()

        class FakeSyncPlaywrightCM:
            def __enter__(self):
                return FakeP()

            def __exit__(self, *a):
                return False

        fake_module = types.ModuleType("playwright.sync_api")
        fake_module.sync_playwright = lambda: FakeSyncPlaywrightCM()

        previous = sys.modules.get("playwright.sync_api")
        previous_pkg = sys.modules.get("playwright")
        sys.modules["playwright"] = types.ModuleType("playwright")
        sys.modules["playwright.sync_api"] = fake_module
        try:
            with tempfile.TemporaryDirectory() as tmp:
                screens_json = Path(tmp) / "screens" / "screens.json"
                screens_json.parent.mkdir(parents=True)
                screens_json.write_text(json.dumps({"capture": {"steps": []}}), encoding="utf-8")
                with self.assertRaises(ScreenError) as ctx:
                    gen_app_screen.run_capture(tmp)
                self.assertIn("Chromium not installed", str(ctx.exception))
                self.assertIn("tools/setup.sh", str(ctx.exception))
        finally:
            if previous is None:
                sys.modules.pop("playwright.sync_api", None)
            else:
                sys.modules["playwright.sync_api"] = previous
            if previous_pkg is None:
                sys.modules.pop("playwright", None)
            else:
                sys.modules["playwright"] = previous_pkg


if __name__ == "__main__":
    unittest.main()
