#!/usr/bin/env python3
"""Pull a published video's public metadata and owner analytics into packaging calibration data.

    python3 tools/yt_stats.py auth
    python3 tools/yt_stats.py fetch <video_id> <project> [--json]

Two APIs, two different things:
  - Data API      (youtube v3)          -> title, publishedAt, duration, views, likes, comments
  - Analytics API (youtubeAnalytics v2) -> avg view %, avg view duration, watch time, subs gained

Auth lives at `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/youtube/`, with its own
`token-analytics.json` and read-only scopes
(`youtube.readonly`, `yt-analytics.readonly`) — never written to the repo.

NOTE ON CTR: impressions / impression click-through rate are not exposed by the YouTube
Analytics API — they are YouTube Studio-only. `ctr` is always written as `null` with
`ctr_source: "manual -- YouTube Studio only"`. Pull it by hand from Studio when calibrating
packaging (see reference/post-production/15-packaging.md §3).

`fetch` merges its result into `{project}/packaging/calibration.json`, keyed by videoId.

Google libraries (`googleapiclient`, `google.oauth2`, `google_auth_oauthlib`) are imported
lazily through `tools/_venv.py`, so the pure helpers below stay importable — and
unit-testable — on a stdlib-only interpreter.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# impressionClickThroughRate is Studio-only and 400s on this endpoint, so it is never
# requested. Kept out on purpose -- do not "helpfully" re-add it.
METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,subscribersGained"

_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


class StatsError(Exception):
    """A yt_stats.py operation cannot proceed (missing setup, bad data, or an API error)."""


def yt_dir() -> Path:
    home = Path(os.environ.get("GASPOL_VIDEO_HOME", str(Path.home() / ".gaspol-video")))
    return home / "youtube"


def client_secret_path() -> Path:
    return yt_dir() / "client_secret.json"


def token_path() -> Path:
    return yt_dir() / "token-analytics.json"


def missing_client_secret_message() -> str:
    secret = client_secret_path()
    steps = [
        "1. create (or reuse) a Google Cloud project",
        "2. enable the YouTube Data API v3 and the YouTube Analytics API for it",
        "3. create an OAuth 2.0 Client ID of type Desktop app",
        f"4. download its JSON and save it to {secret}",
    ]
    return "missing client secret at " + str(secret) + "; setup:\n" + "\n".join(f"  {s}" for s in steps)


def check_client_secret():
    """Return the setup message when client_secret.json is missing, else None."""
    if client_secret_path().exists():
        return None
    return missing_client_secret_message()


def iso8601_to_minutes(duration):
    """"PT5M30S" -> 5.5. Returns None for anything that doesn't parse."""
    if not duration:
        return None
    match = _DURATION_RE.fullmatch(duration)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return round(hours * 60 + minutes + seconds / 60, 1)


def merge_calibration(existing: dict, entry: dict) -> dict:
    """Merge `entry` into `existing["videos"]` by videoId, replacing any prior entry for
    the same video and leaving every other video untouched."""
    videos = [v for v in (existing or {}).get("videos", []) if v.get("videoId") != entry.get("videoId")]
    videos.append(entry)
    return {"videos": videos}


def analytics_row_to_fields(column_headers, row) -> dict:
    """Turn one Analytics API report row into the calibration fields it fills.

    `column_headers` is the API's `columnHeaders` list (each `{"name": ...}` or a bare
    name string); `row` is the matching values list from `rows[0]`.
    """
    names = [h["name"] if isinstance(h, dict) else h for h in column_headers]
    values = dict(zip(names, row))

    avg_pct = values.get("averageViewPercentage")
    minutes_watched = values.get("estimatedMinutesWatched")
    return {
        "avgViewPct": round(avg_pct, 1) if avg_pct is not None else None,
        "avgViewDurationS": values.get("averageViewDuration"),
        "watchTimeH": round(minutes_watched / 60, 1) if minutes_watched is not None else None,
        "subsGained": values.get("subscribersGained"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_creds():
    """Load, refresh, or newly obtain OAuth credentials for the read-only scopes."""
    request_mod = _venv.require("google.auth.transport.requests")
    creds_mod = _venv.require("google.oauth2.credentials")
    flow_mod = _venv.require("google_auth_oauthlib.flow")
    Request = request_mod.Request
    Credentials = creds_mod.Credentials
    InstalledAppFlow = flow_mod.InstalledAppFlow

    token = token_path()
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        message = check_client_secret()
        if message:
            raise StatsError(message)
        creds = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path()), SCOPES
        ).run_local_server(port=0)

    yt_dir().mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def fetch(video_id: str) -> dict:
    """Pull public stats (Data API) and, when available, owner analytics for `video_id`."""
    discovery_mod = _venv.require("googleapiclient.discovery")
    errors_mod = _venv.require("googleapiclient.errors")
    build = discovery_mod.build
    HttpError = errors_mod.HttpError

    creds = get_creds()
    youtube = build("youtube", "v3", credentials=creds)
    items = (
        youtube.videos()
        .list(part="snippet,statistics,contentDetails", id=video_id)
        .execute()
        .get("items", [])
    )
    if not items:
        raise StatsError(f"video {video_id} not found (or not visible to this account)")

    video = items[0]
    snippet, stats, content_details = video["snippet"], video.get("statistics", {}), video["contentDetails"]
    published_at = snippet["publishedAt"]

    entry = {
        "videoId": video_id,
        "title": snippet["title"],
        "publishedAt": published_at,
        "durationMin": iso8601_to_minutes(content_details.get("duration")),
        "views": int(stats["viewCount"]) if "viewCount" in stats else None,
        "likes": int(stats["likeCount"]) if "likeCount" in stats else None,
        "comments": int(stats["commentCount"]) if "commentCount" in stats else None,
        "avgViewPct": None,
        "avgViewDurationS": None,
        "watchTimeH": None,
        "subsGained": None,
        "ctr": None,
        "ctr_source": "manual -- YouTube Studio only",
        "fetched_at": _now_iso(),
    }

    start_date = published_at[:10]
    end_date = datetime.now(timezone.utc).date().isoformat()
    try:
        analytics = build("youtubeAnalytics", "v2", credentials=creds)
        report = (
            analytics.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=METRICS,
                filters=f"video=={video_id}",
            )
            .execute()
        )
        if report.get("rows"):
            entry.update(analytics_row_to_fields(report["columnHeaders"], report["rows"][0]))
    except HttpError as exc:
        print(
            f"yt_stats: analytics unavailable ({exc}); public stats only. "
            "Run `python3 tools/yt_stats.py auth` if the analytics scope has not been "
            "consented to yet.",
            file=sys.stderr,
        )

    return entry


def _write_calibration(project, entry) -> Path:
    calibration_path = Path(project) / "packaging" / "calibration.json"
    existing = {}
    if calibration_path.exists():
        try:
            existing = json.loads(calibration_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StatsError(f"{calibration_path}: invalid JSON ({exc})") from exc
    merged = merge_calibration(existing, entry)
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return calibration_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("auth")

    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("video_id")
    fetch_parser.add_argument("project")
    fetch_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.mode == "auth":
            get_creds()
            print(f"authorized -- token saved to {token_path()}")
            return 0

        entry = fetch(args.video_id)
        calibration_path = _write_calibration(args.project, entry)

        if args.json:
            print(json.dumps(entry, indent=2, ensure_ascii=False))
        else:
            for key, value in entry.items():
                print(f"  {key:<14} {value if value is not None else '-'}")
            print(f"\n  note: ctr is YouTube Studio-only. wrote {calibration_path}")
        return 0
    except _venv.DependencyMissing as exc:
        print(f"yt_stats: {exc}", file=sys.stderr)
        return 2
    except StatsError as exc:
        print(f"yt_stats: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
