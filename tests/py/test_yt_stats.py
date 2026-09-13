import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tools import yt_stats


def _install_fake_google_modules(raise_refresh_error=False):
    """Register minimal fake `google.*` / `google_auth_oauthlib.*` modules in sys.modules
    so `tools._venv.require(name)` finds them via plain `importlib.import_module` — no real
    google-api-python-client / google-auth install needed to exercise get_creds()'s wiring.
    Returns a teardown() that removes exactly what this installed.
    """
    class FakeGoogleAuthError(Exception):
        pass

    class FakeRefreshError(FakeGoogleAuthError):
        pass

    class FakeCreds:
        def __init__(self, valid=False, expired=True, refresh_token="rt"):
            self.valid = valid
            self.expired = expired
            self.refresh_token = refresh_token

        def refresh(self, request):
            if raise_refresh_error:
                raise FakeRefreshError("revoked")
            self.valid = True

        def to_json(self):
            return '{"token": "fake"}'

    fake_creds_holder = {"instance": FakeCreds()}

    class FakeCredentials:
        @staticmethod
        def from_authorized_user_file(path, scopes):
            return fake_creds_holder["instance"]

    requests_mod = types.ModuleType("google.auth.transport.requests")
    requests_mod.Request = lambda: None

    exceptions_mod = types.ModuleType("google.auth.exceptions")
    exceptions_mod.GoogleAuthError = FakeGoogleAuthError
    exceptions_mod.RefreshError = FakeRefreshError

    credentials_mod = types.ModuleType("google.oauth2.credentials")
    credentials_mod.Credentials = FakeCredentials

    flow_mod = types.ModuleType("google_auth_oauthlib.flow")
    flow_mod.InstalledAppFlow = None  # not exercised in these tests

    names = {
        "google": types.ModuleType("google"),
        "google.auth": types.ModuleType("google.auth"),
        "google.auth.transport": types.ModuleType("google.auth.transport"),
        "google.auth.transport.requests": requests_mod,
        "google.auth.exceptions": exceptions_mod,
        "google.oauth2": types.ModuleType("google.oauth2"),
        "google.oauth2.credentials": credentials_mod,
        "google_auth_oauthlib": types.ModuleType("google_auth_oauthlib"),
        "google_auth_oauthlib.flow": flow_mod,
    }
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules.update(names)

    def teardown():
        for name, mod in previous.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    return teardown, fake_creds_holder


def _with_gaspol_video_home(value):
    """Context manager-ish helper: returns (setup, teardown) closures for a patched env."""
    before = os.environ.get("GASPOL_VIDEO_HOME")

    def teardown():
        if before is None:
            os.environ.pop("GASPOL_VIDEO_HOME", None)
        else:
            os.environ["GASPOL_VIDEO_HOME"] = before

    os.environ["GASPOL_VIDEO_HOME"] = value
    return teardown


class Iso8601ToMinutesTest(unittest.TestCase):
    def test_minutes_and_seconds(self):
        self.assertEqual(yt_stats.iso8601_to_minutes("PT5M30S"), 5.5)

    def test_hours_and_minutes(self):
        self.assertEqual(yt_stats.iso8601_to_minutes("PT1H2M"), 62.0)

    def test_invalid_duration_returns_none(self):
        self.assertIsNone(yt_stats.iso8601_to_minutes("not-a-duration"))

    def test_empty_or_missing_duration_returns_none(self):
        self.assertIsNone(yt_stats.iso8601_to_minutes(""))
        self.assertIsNone(yt_stats.iso8601_to_minutes(None))

    def test_hours_only(self):
        self.assertEqual(yt_stats.iso8601_to_minutes("PT2H"), 120.0)


class MergeCalibrationTest(unittest.TestCase):
    def test_replaces_same_video_id_keeps_others(self):
        existing = {
            "videos": [
                {"videoId": "abc", "views": 100},
                {"videoId": "def", "views": 200},
            ]
        }
        merged = yt_stats.merge_calibration(existing, {"videoId": "abc", "views": 999})
        by_id = {v["videoId"]: v for v in merged["videos"]}
        self.assertEqual(len(merged["videos"]), 2)
        self.assertEqual(by_id["abc"]["views"], 999)
        self.assertEqual(by_id["def"]["views"], 200)

    def test_appends_new_video_id(self):
        existing = {"videos": [{"videoId": "abc", "views": 100}]}
        merged = yt_stats.merge_calibration(existing, {"videoId": "xyz", "views": 5})
        self.assertEqual({v["videoId"] for v in merged["videos"]}, {"abc", "xyz"})

    def test_empty_existing_document(self):
        merged = yt_stats.merge_calibration({}, {"videoId": "abc"})
        self.assertEqual(merged, {"videos": [{"videoId": "abc"}]})

    def test_missing_videos_key_treated_as_empty(self):
        merged = yt_stats.merge_calibration({"other": 1}, {"videoId": "abc"})
        self.assertEqual(merged["videos"], [{"videoId": "abc"}])


class AnalyticsRowToFieldsTest(unittest.TestCase):
    def test_rounds_avg_view_pct_and_watch_time_hours(self):
        headers = [
            {"name": "averageViewPercentage"},
            {"name": "estimatedMinutesWatched"},
            {"name": "averageViewDuration"},
            {"name": "subscribersGained"},
        ]
        row = [42.567, 125, 33, 4]
        fields = yt_stats.analytics_row_to_fields(headers, row)
        self.assertEqual(fields["avgViewPct"], 42.6)
        self.assertEqual(fields["watchTimeH"], round(125 / 60, 1))
        self.assertEqual(fields["avgViewDurationS"], 33)
        self.assertEqual(fields["subsGained"], 4)

    def test_handles_bare_string_headers(self):
        headers = ["averageViewPercentage", "estimatedMinutesWatched"]
        row = [10.0, 60]
        fields = yt_stats.analytics_row_to_fields(headers, row)
        self.assertEqual(fields["avgViewPct"], 10.0)
        self.assertEqual(fields["watchTimeH"], 1.0)

    def test_missing_metric_is_none(self):
        headers = [{"name": "averageViewPercentage"}]
        row = [None]
        fields = yt_stats.analytics_row_to_fields(headers, row)
        self.assertIsNone(fields["avgViewPct"])
        self.assertIsNone(fields["watchTimeH"])


class WriteTokenTest(unittest.TestCase):
    def test_token_file_written_0600_inside_a_0700_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            teardown = _with_gaspol_video_home(tmp)
            try:
                class FakeCreds:
                    def to_json(self):
                        return '{"token": "x"}'

                yt_stats._write_token(FakeCreds())

                token = yt_stats.token_path()
                self.assertTrue(token.exists())
                self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)

                ydir = yt_stats.yt_dir()
                self.assertEqual(stat.S_IMODE(ydir.stat().st_mode), 0o700)
            finally:
                teardown()


class GetCredsErrorWrappingTest(unittest.TestCase):
    def test_refresh_error_is_wrapped_with_an_actionable_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            teardown_home = _with_gaspol_video_home(tmp)
            teardown_google, _holder = _install_fake_google_modules(raise_refresh_error=True)
            try:
                token = yt_stats.token_path()
                token.parent.mkdir(parents=True, exist_ok=True)
                token.write_text("{}", encoding="utf-8")

                with self.assertRaises(yt_stats.StatsError) as ctx:
                    yt_stats.get_creds()
                self.assertIn("token revoked or expired", str(ctx.exception))
                self.assertIn("tools/yt_stats.py auth", str(ctx.exception))
            finally:
                teardown_google()
                teardown_home()


class ClientSecretCheckTest(unittest.TestCase):
    def test_missing_client_secret_lists_four_setup_steps(self):
        teardown = _with_gaspol_video_home("/tmp/gaspol-video-test-yt-home-missing")
        try:
            message = yt_stats.check_client_secret()
            self.assertIsNotNone(message)
            for marker in ("1.", "2.", "3.", "4."):
                self.assertIn(marker, message)
            self.assertIn("client_secret.json", message)
            self.assertIn("YouTube Data API v3", message)
            self.assertIn("YouTube Analytics API", message)
        finally:
            teardown()

    def test_no_message_when_client_secret_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            teardown = _with_gaspol_video_home(tmp)
            try:
                secret = Path(tmp) / "youtube" / "client_secret.json"
                secret.parent.mkdir(parents=True)
                secret.write_text("{}", encoding="utf-8")
                self.assertIsNone(yt_stats.check_client_secret())
            finally:
                teardown()

    def test_yt_dir_honours_gaspol_video_home(self):
        teardown = _with_gaspol_video_home("/tmp/gaspol-video-test-yt-home")
        try:
            self.assertEqual(str(yt_stats.yt_dir()), "/tmp/gaspol-video-test-yt-home/youtube")
        finally:
            teardown()


if __name__ == "__main__":
    unittest.main()
