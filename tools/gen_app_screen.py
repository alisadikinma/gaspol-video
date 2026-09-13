#!/usr/bin/env python3
"""Produce believable app-screen PNGs for ref/ — captured from a real URL or rendered from a TSX mock.

    python3 tools/gen_app_screen.py capture <project> [--headed]
    python3 tools/gen_app_screen.py mock <project> [--only name]

`capture` drives a real Chromium session (Playwright) through the steps in
`{project}/screens/screens.json` and screenshots the pages named `shot`. `mock` renders a
Remotion TSX component per state through `shots/scripts/render-stills.mjs`, for a screen that
does not exist yet or cannot be reached. Both write `{project}/ref/ui-<name>[-<state>].png` and
merge an entry into `{project}/screens/manifest.json` keyed by screen name.

Security: `screens.json` never carries arbitrary JavaScript (no `eval` step) and never carries
credentials (a `fill` step whose selector or value looks like a secret is refused) — log into the
real app once with `--headed` against a persistent `browser_profile` instead.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

SCREENS_JSON_REL = Path("screens") / "screens.json"
MANIFEST_REL = Path("screens") / "manifest.json"

ALLOWED_ACTION_KEYS = {"goto", "wait", "wait_for", "click", "fill", "press", "scroll", "shot"}
ALLOWED_META_KEYS = {"optional", "timeout", "url_label", "title"}
ALL_ALLOWED_KEYS = ALLOWED_ACTION_KEYS | ALLOWED_META_KEYS

CREDENTIAL_KEYWORDS = ("password", "passwd", "token", "secret")
SHOT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ScreenError(Exception):
    """A screens.json spec, or a step in it, cannot be turned into a screenshot."""


def _looks_like_credential(selector, value) -> bool:
    haystack = f"{selector} {value}".lower()
    return any(keyword in haystack for keyword in CREDENTIAL_KEYWORDS)


def validate_steps(steps):
    """Normalise and validate a `capture.steps` list. Raises ScreenError on anything unsafe
    or unrecognised: an unknown key (including `eval`, which is never allowed), a credential-
    looking `fill`, a malformed or duplicate `shot` name."""
    if not isinstance(steps, list):
        raise ScreenError("capture.steps must be a list")

    normalised = []
    seen_shot_names = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ScreenError(f"unknown step {i}: not an object")

        keys = set(step.keys())
        unknown = keys - ALL_ALLOWED_KEYS
        action_keys = keys & ALLOWED_ACTION_KEYS
        if unknown or len(action_keys) != 1:
            raise ScreenError(f"unknown step {i}: {sorted(keys)}")

        action = next(iter(action_keys))

        if action == "fill":
            value = step["fill"]
            if not (isinstance(value, list) and len(value) == 2):
                raise ScreenError(f"step {i}: fill needs [selector, value]")
            selector, fill_value = value
            if _looks_like_credential(selector, fill_value):
                raise ScreenError(
                    "do not put credentials in screens.json; log in once with --headed "
                    "and a browser_profile"
                )

        if action == "shot":
            name = step["shot"]
            if not isinstance(name, str) or not SHOT_NAME_RE.match(name):
                raise ScreenError(f"step {i}: bad shot name {name!r}")
            if name in seen_shot_names:
                raise ScreenError(f"step {i}: duplicate shot name {name!r}")
            seen_shot_names.add(name)

        normalised.append(dict(step))

    return normalised


def shot_path(project, name) -> Path:
    return Path(project) / "ref" / f"ui-{name}.png"


def merge_manifest(existing, new_entries):
    """Merge `new_entries` into `existing` by `name`. Entries not touched by `new_entries`
    (e.g. mock screens while capturing, or vice versa) are kept untouched."""
    new_by_name = {e["name"]: e for e in new_entries}
    merged = []
    seen = set()
    for entry in existing:
        name = entry.get("name")
        if name in new_by_name:
            merged.append(new_by_name[name])
            seen.add(name)
        else:
            merged.append(entry)
    for entry in new_entries:
        if entry["name"] not in seen:
            merged.append(entry)
    return merged


def load_screens_json(project) -> dict:
    path = Path(project) / SCREENS_JSON_REL
    if not path.exists():
        raise ScreenError(f"{path} not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScreenError(f"{path}: invalid JSON ({exc})") from exc


def capture_spec(config: dict) -> dict:
    capture = config.get("capture")
    if capture is None:
        raise ScreenError("screens.json has no capture block")
    return capture


def write_manifest(project, new_entries) -> None:
    path = Path(project) / MANIFEST_REL
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8")).get("screens", [])
        except json.JSONDecodeError:
            existing = []
    merged = merge_manifest(existing, new_entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"screens": merged}, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_capture(project, headed=False):
    """Drive Playwright through `capture.steps`, screenshot every `shot`, return the new
    manifest entries. Playwright is imported here, not at module import time, so the pure
    functions above (and their tests) never need it installed."""
    playwright_api = _venv.require("playwright.sync_api")
    sync_playwright = playwright_api.sync_playwright

    config = load_screens_json(project)
    capture = capture_spec(config)
    steps = validate_steps(capture.get("steps", []))

    viewport = config.get("viewport", [1920, 1080])
    device_scale = config.get("device_scale", 1)
    base_url = capture.get("base_url", "")
    browser_profile = capture.get("browser_profile")

    entries = []
    shot_count = 0

    with sync_playwright() as p:
        viewport_size = {"width": viewport[0], "height": viewport[1]}
        if browser_profile:
            profile_dir = Path(browser_profile).expanduser()
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=not headed,
                viewport=viewport_size,
                device_scale_factor=device_scale,
            )
            browser = None
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context(viewport=viewport_size, device_scale_factor=device_scale)
            page = context.new_page()

        try:
            for i, step in enumerate(steps):
                if "goto" in step:
                    url = step["goto"]
                    full_url = url if url.startswith("http") else base_url.rstrip("/") + "/" + url.lstrip("/")
                    print(f"step {i:02d} goto {full_url}")
                    page.goto(full_url)
                elif "wait" in step:
                    ms = step["wait"]
                    print(f"step {i:02d} wait {ms}")
                    page.wait_for_timeout(ms)
                elif "wait_for" in step:
                    selector = step["wait_for"]
                    print(f"step {i:02d} wait_for {selector}")
                    page.wait_for_selector(selector, timeout=30000)
                elif "click" in step:
                    selector = step["click"]
                    optional = step.get("optional", False)
                    timeout = step.get("timeout", 30000)
                    print(f"step {i:02d} click {selector}")
                    try:
                        page.click(selector, timeout=timeout)
                    except Exception as exc:  # noqa: BLE001 - re-raised unless optional
                        if optional:
                            print(f"  optional click skipped: {selector}")
                        else:
                            raise ScreenError(f"step {i}: click {selector} failed: {exc}") from exc
                elif "fill" in step:
                    selector, value = step["fill"]
                    print(f"step {i:02d} fill {selector}")
                    page.fill(selector, value)
                elif "press" in step:
                    key = step["press"]
                    print(f"step {i:02d} press {key}")
                    page.keyboard.press(key)
                elif "scroll" in step:
                    amount = step["scroll"]
                    print(f"step {i:02d} scroll {amount}")
                    page.mouse.wheel(0, amount)
                elif "shot" in step:
                    name = step["shot"]
                    out_path = shot_path(project, name)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(out_path))
                    shot_count += 1
                    print(f"shot [{shot_count:02d}] {out_path.name}")
                    entries.append(
                        {
                            "name": name,
                            "file": out_path.name,
                            "url_label": step.get("url_label", ""),
                            "title": step.get("title", ""),
                            "source": "capture",
                            "simulated": False,
                            "captured_at": _now_iso(),
                        }
                    )
        finally:
            context.close()
            if browser is not None:
                browser.close()

    return entries


def _cli_capture(args) -> int:
    try:
        entries = run_capture(args.project, headed=args.headed)
    except _venv.DependencyMissing as exc:
        print(f"gen_app_screen: {exc}", file=sys.stderr)
        return 2
    except ScreenError as exc:
        print(f"gen_app_screen: {exc}", file=sys.stderr)
        return 1

    if not entries:
        print("gen_app_screen: no shots captured", file=sys.stderr)
        return 1

    write_manifest(args.project, entries)
    print(f"captured {len(entries)} screen(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    capture_ap = sub.add_parser("capture")
    capture_ap.add_argument("project")
    capture_ap.add_argument("--headed", action="store_true")

    args = ap.parse_args(argv)

    if args.mode == "capture":
        return _cli_capture(args)

    print(f"gen_app_screen: unknown mode {args.mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
