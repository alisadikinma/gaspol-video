"""Layout profiles for short vertical video: safe area and text defaults.

Every number in media/layout-profiles.json carries a `source` that starts with
`official:`, `data:` or `tafsiran:` so the origin of each value stays visible.
"""
import copy
import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "media" / "layout-profiles.json"
SOURCE_PREFIXES = ("official:", "data:", "tafsiran:")
EDGES = ("left", "top", "right", "bottom")


def _read(path):
    path = Path(path)
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path.name}: malformed JSON: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name}: top level must be an object")
    return doc


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and "source" not in v:
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve(name, profiles, seen=()):
    if name not in profiles:
        raise KeyError(f"unknown profile {name!r}; valid: {', '.join(sorted(profiles))}")
    if name in seen:
        raise ValueError(f"inherits cycle: {' -> '.join(seen + (name,))}")
    prof = profiles[name]
    parent = prof.get("inherits")
    if parent is None:
        return copy.deepcopy(prof)
    base = _resolve(parent, profiles, seen + (name,))
    merged = _merge(base, {k: v for k, v in prof.items() if k != "inherits"})
    return merged


def load(name, path=None):
    path = Path(path) if path else DEFAULT_PATH
    doc = _read(path)
    profiles = doc.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError(f"{path.name}: missing 'profiles' object")
    return _resolve(name, profiles)


def safe_box(profile):
    w, h = profile["width"], profile["height"]
    safe = profile["safe"]
    for e in EDGES:
        if e not in safe:
            raise KeyError(f"safe.{e} missing")
    x0 = round(safe["left"]["pct"] * w)
    y0 = round(safe["top"]["pct"] * h)
    x1 = w - round(safe["right"]["pct"] * w)
    y1 = h - round(safe["bottom"]["pct"] * h)
    return (x0, y0, x1, y1)


def value(profile, dotted_key):
    node = profile
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"no key {dotted_key!r} in profile")
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    if isinstance(node, dict) and "pct" in node:
        return node["pct"]
    return node


def _leaves(node, trail, problems):
    if not isinstance(node, dict):
        return
    if "pct" in node or "value" in node:
        src = node.get("source")
        if not isinstance(src, str) or not src.strip():
            problems.append(f"{trail}: number without source")
        elif not src.startswith(SOURCE_PREFIXES):
            problems.append(f"{trail}: source must start with official:, data: or tafsiran:")
        return
    for k, v in node.items():
        _leaves(v, f"{trail}.{k}", problems)


def validate(doc):
    profiles = doc.get("profiles") if isinstance(doc, dict) else None
    if not isinstance(profiles, dict):
        return ["missing 'profiles' object"]
    problems = []
    for name, prof in profiles.items():
        parent = prof.get("inherits")
        if parent is not None and parent not in profiles:
            problems.append(f"{name}: inherits unknown profile {parent!r}")
        for k, v in prof.items():
            if k != "inherits":
                _leaves(v, f"{name}.{k}", problems)
    return problems


THRESHOLD = 16


def text_box(png_path, background=0):
    """Extent of the pixels that differ from `background`: [x0, y0, x1, y1], end exclusive.

    `background` is a gray level 0-255 (default 0 = black). A pixel counts when its gray
    value is more than 16 away from it. Measure text with a dark outline on a mid-grey
    background (0x80): on black the outline is invisible and the box comes out too tight.
    Returns None when nothing differs. The image is decoded by ffmpeg to raw gray, so any
    format ffmpeg reads works.
    """
    from . import ff
    video = ff.probe(png_path)["video"]
    if not video:
        raise ValueError(f"{png_path}: no picture")
    w, h = video["width"], video["height"]
    raw = ff.run_bytes(["ffmpeg", "-v", "error", "-i", png_path, "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    if len(raw) < w * h:
        raise ValueError(f"{png_path}: short raw read ({len(raw)} of {w * h} bytes)")
    table = bytes(1 if abs(i - background) > THRESHOLD else 0 for i in range(256))
    x0 = y0 = x1 = y1 = None
    for y in range(h):
        row = raw[y * w:(y + 1) * w].translate(table)
        first = row.find(1)
        if first < 0:
            continue
        last = row.rfind(1)
        if y0 is None:
            y0 = y
        y1 = y + 1
        x0 = first if x0 is None else min(x0, first)
        x1 = last + 1 if x1 is None else max(x1, last + 1)
    return None if y0 is None else [x0, y0, x1, y1]
