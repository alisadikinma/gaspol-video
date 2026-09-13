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
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

SCREENS_JSON_REL = Path("screens") / "screens.json"
MANIFEST_REL = Path("screens") / "manifest.json"
DATA_JSON_REL = Path("screens") / "data.json"
TEMPLATE_BRAND_PATH = Path(__file__).resolve().parent.parent / "templates" / "remotion" / "brand.json"

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


def is_placeholder_brand(brand: dict, template: dict) -> bool:
    """True when every real field of `brand` (everything but `_comment`) still equals the
    shipped template's value — i.e. nobody has written the client's brand yet."""
    keys = [k for k in template if k != "_comment"]
    return all(brand.get(k) == template.get(k) for k in keys)


def mock_jobs(spec, data, project, only=None):
    """Expand a `screens.json` `mock` list into one render job per (screen, state).

    `spec` is the `mock` list itself (each entry: name, component, states, ...). `data` is
    the parsed `screens/data.json`. Raises ScreenError when a screen has no data.json key,
    when its component .tsx file is missing, or when a state name is invalid.
    """
    jobs = []
    for entry in spec:
        name = entry["name"]
        if only is not None and name != only:
            continue
        component = entry["component"]
        if name not in data:
            raise ScreenError(f"data.json has no key for screen {name!r}")
        component_file = Path(project) / "shots" / "src" / "shots" / "screens" / f"{component}.tsx"
        if not component_file.exists():
            raise ScreenError(f"missing component file: {component_file}")
        for state in entry.get("states", []):
            if not isinstance(state, str) or not SHOT_NAME_RE.match(state):
                raise ScreenError(f"bad state name for {name!r}: {state!r}")
            jobs.append(
                {
                    "component": component,
                    "props": {"state": state, "data": data[name]},
                    "out": str(shot_path(project, f"{name}-{state}")),
                    "name": name,
                    "state": state,
                    "data_key": name,
                    "url_label": entry.get("url_label", ""),
                    "title": entry.get("title", ""),
                }
            )
    return jobs


def run_mock(project, only=None):
    """Render one PNG per (mock screen, state) through the project's Remotion workspace.

    Requires the workspace at `{project}/shots/` to already be scaffolded, `npm install`ed,
    and its `src/shots/brand.json` written with real (non-placeholder) values."""
    shots_dir = Path(project) / "shots"
    brand_path = shots_dir / "src" / "shots" / "brand.json"
    if not brand_path.exists():
        raise ScreenError(f"{brand_path} not found; scaffold the shots workspace first")

    brand = json.loads(brand_path.read_text(encoding="utf-8"))
    template = json.loads(TEMPLATE_BRAND_PATH.read_text(encoding="utf-8"))
    if is_placeholder_brand(brand, template):
        raise ScreenError("brand.json still holds template placeholders; write it from strategic-brief.md first")

    config = load_screens_json(project)
    mock_spec = config.get("mock")
    if not mock_spec:
        raise ScreenError("screens.json has no mock block")

    data_path = Path(project) / DATA_JSON_REL
    if not data_path.exists():
        raise ScreenError(f"{data_path} not found")
    data = json.loads(data_path.read_text(encoding="utf-8"))

    jobs = mock_jobs(mock_spec, data, project, only=only)
    if not jobs:
        raise ScreenError("no mock jobs matched")

    node = shutil.which("node")
    if node is None:
        raise ScreenError("node not found")

    gen_proc = subprocess.run(
        [node, "scripts/gen-registry.mjs"], cwd=str(shots_dir), capture_output=True, text=True
    )
    if gen_proc.returncode != 0:
        raise ScreenError(f"gen-registry failed:\n{gen_proc.stderr.strip()[-800:]}")

    entries = []
    for job in jobs:
        out_path = Path(job["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"mock {job['name']}/{job['state']} -> {out_path.relative_to(project)}")
        proc = subprocess.run(
            [node, "scripts/render-stills.mjs", job["component"], "--props", json.dumps(job["props"]), "--out", str(out_path)],
            cwd=str(shots_dir),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip()[-800:]
            if "@remotion/renderer" in proc.stderr or "Cannot find module" in proc.stderr:
                raise ScreenError(f"run `npm install` in {shots_dir} first:\n{stderr_tail}")
            raise ScreenError(f"render-stills failed:\n{stderr_tail}")

        entries.append(
            {
                "name": job["name"],
                "file": out_path.name,
                "url_label": job["url_label"],
                "title": job["title"],
                "source": "mock",
                "simulated": True,
                "component": job["component"],
                "state": job["state"],
                "data_key": job["data_key"],
                "captured_at": _now_iso(),
            }
        )
    return entries


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


def run_steps(page, steps, project, base_url):
    """Execute `steps` against `page` (a Playwright Page, or any object with the same
    goto/wait_for_timeout/wait_for_selector/click/fill/keyboard.press/mouse.wheel/screenshot
    surface — a fake in tests). Returns `(entries, shot_count)`.

    Every step failure is wrapped as `ScreenError(f"step {i:02d} {key}: {message}")` so a
    broken step names itself and its position instead of leaking a raw Playwright traceback.
    An optional `click` that fails is the one exception: it is logged and skipped, not raised.
    """
    entries = []
    shot_count = 0

    for i, step in enumerate(steps):
        key = next(iter(k for k in step if k in ALLOWED_ACTION_KEYS))
        try:
            if key == "goto":
                url = step["goto"]
                full_url = url if url.startswith("http") else base_url.rstrip("/") + "/" + url.lstrip("/")
                print(f"step {i:02d} goto {full_url}")
                page.goto(full_url)
            elif key == "wait":
                ms = step["wait"]
                print(f"step {i:02d} wait {ms}")
                page.wait_for_timeout(ms)
            elif key == "wait_for":
                selector = step["wait_for"]
                print(f"step {i:02d} wait_for {selector}")
                page.wait_for_selector(selector, timeout=30000)
            elif key == "click":
                selector = step["click"]
                optional = step.get("optional", False)
                timeout = step.get("timeout", 30000)
                print(f"step {i:02d} click {selector}")
                try:
                    page.click(selector, timeout=timeout)
                except Exception as exc:  # noqa: BLE001 - swallowed only when optional
                    if optional:
                        print(f"  optional click skipped: {selector}")
                    else:
                        raise
            elif key == "fill":
                selector, value = step["fill"]
                print(f"step {i:02d} fill {selector}")
                page.fill(selector, value)
            elif key == "press":
                press_key = step["press"]
                print(f"step {i:02d} press {press_key}")
                page.keyboard.press(press_key)
            elif key == "scroll":
                amount = step["scroll"]
                print(f"step {i:02d} scroll {amount}")
                page.mouse.wheel(0, amount)
            elif key == "shot":
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
        except ScreenError:
            raise
        except Exception as exc:
            raise ScreenError(f"step {i:02d} {key}: {exc}") from exc

    return entries, shot_count


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
            entries, _shot_count = run_steps(page, steps, project, base_url)
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


def _cli_mock(args) -> int:
    try:
        entries = run_mock(args.project, only=args.only)
    except ScreenError as exc:
        print(f"gen_app_screen: {exc}", file=sys.stderr)
        return 1

    write_manifest(args.project, entries)
    print(f"rendered {len(entries)} mock screen(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    capture_ap = sub.add_parser("capture")
    capture_ap.add_argument("project")
    capture_ap.add_argument("--headed", action="store_true")

    mock_ap = sub.add_parser("mock")
    mock_ap.add_argument("project")
    mock_ap.add_argument("--only")

    args = ap.parse_args(argv)

    if args.mode == "capture":
        return _cli_capture(args)
    if args.mode == "mock":
        return _cli_mock(args)

    print(f"gen_app_screen: unknown mode {args.mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
