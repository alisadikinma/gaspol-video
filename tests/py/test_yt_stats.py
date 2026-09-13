import os
import tempfile
import unittest
from pathlib import Path

from tools import yt_stats


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
