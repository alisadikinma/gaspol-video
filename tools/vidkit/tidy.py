"""Read-only scan of a project folder against the folder contract.

``scan`` reports stray folders and subfolders, duplicate files, stale ledger entries, old
``.tmp`` files and MCP renders that were not moved home. It never writes.
"""
import hashlib
import os
import time
from pathlib import Path

from tools import renders

CONTRACT_DIRS = {"ref", "keyframes", "shots", "clips", "vo", "sfx", "work", "output", "_arsip",
                 ".tmp", "screens", "packaging"}
DUP_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "output", "_arsip")
MCP_SUBDIRS = (".tmp/image", ".tmp/video")
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mp3", ".wav"}
FLAT_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "_arsip")
ALLOWED_SUBDIRS = {"output": {"stems"}}

_KEYS = ("unknown_dirs", "unknown_subdirs", "duplicates", "stale_ledger", "old_tmp",
         "unmoved_mcp", "mcp_already_home", "unreadable")


def _check_project(project):
    root = Path(project)
    if not root.is_dir():
        raise ValueError(f"not a directory: {project}")
    if (root / ".tmp").is_symlink():
        raise ValueError(f".tmp is a symlink: {root / '.tmp'}")
    return root


def _entries(path):
    try:
        with os.scandir(path) as it:
            return sorted(it, key=lambda e: e.name)
    except OSError:
        return []


def _rel(root, path):
    return Path(path).relative_to(root).as_posix()


def _files(root, rel_dir):
    """Regular files (no symlinks, no symlinked dirs) below root/rel_dir, sorted."""
    out = []
    start = root / rel_dir
    if start.is_symlink() or not start.is_dir():
        return out
    for dp, dn, fn in os.walk(start, followlinks=False):
        dn[:] = sorted(d for d in dn if not os.path.islink(os.path.join(dp, d)))
        for n in sorted(fn):
            p = os.path.join(dp, n)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            out.append(p)
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_groups(paths, unreadable):
    """Group paths by identical bytes. Size first; hash only same-size sets; skip size 0."""
    by_size = {}
    for p in paths:
        try:
            size = os.stat(p).st_size
        except OSError:
            unreadable.add(p)
            continue
        if size == 0:
            continue
        by_size.setdefault(size, []).append(p)
    groups = {}
    for same in by_size.values():
        if len(same) < 2:
            continue
        for p in same:
            try:
                groups.setdefault(_sha256(p), []).append(p)
            except OSError:
                unreadable.add(p)
    return groups


def scan(project, tmp_days=7, now=None):
    root = _check_project(project)
    now = time.time() if now is None else now
    report = {k: [] for k in _KEYS}

    for e in _entries(root):
        if e.name.startswith(".") or e.name in CONTRACT_DIRS:
            continue
        if e.is_dir(follow_symlinks=False) or (e.is_symlink() and e.is_dir()):
            report["unknown_dirs"].append(e.name)

    for d in FLAT_DIRS + tuple(ALLOWED_SUBDIRS):
        base = root / d
        if base.is_symlink() or not base.is_dir():
            continue
        allowed = ALLOWED_SUBDIRS.get(d, set())
        for e in _entries(base):
            if e.name in allowed:
                continue
            if e.is_dir(follow_symlinks=False) or (e.is_symlink() and e.is_dir()):
                report["unknown_subdirs"].append(f"{d}/{e.name}")
    report["unknown_subdirs"].sort()

    unreadable = set()
    home = []
    for d in DUP_DIRS:
        home.extend(_files(root, d))
    mcp = []
    for d in MCP_SUBDIRS:
        mcp.extend(p for p in _files(root, d) if Path(p).suffix.lower() in MEDIA_EXT)
    groups = _hash_groups(home + mcp, unreadable)
    home_set = set(home)
    for paths in groups.values():
        in_home = sorted(_rel(root, p) for p in paths if p in home_set)
        in_mcp = sorted(_rel(root, p) for p in paths if p not in home_set)
        if len(in_home) >= 2:
            report["duplicates"].append(in_home)
        if in_home:
            for m in in_mcp:
                report["mcp_already_home"].append(f"{m} = {in_home[0]}")
    already = {e.split(" = ")[0] for e in report["mcp_already_home"]}
    for p in mcp:
        rel = _rel(root, p)
        if rel in already or p in unreadable:
            continue
        report["unmoved_mcp"].append(rel)
    report["duplicates"].sort()
    report["mcp_already_home"].sort()
    report["unmoved_mcp"].sort()

    try:
        ledger = renders.load(root)
    except renders.RenderLedgerError as exc:
        report["stale_ledger"] = [f"renders.json: {exc}"]
    else:
        for entry in ledger["renders"]:
            if not isinstance(entry, dict) or entry.get("status") != "done":
                continue
            f = entry.get("file")
            if isinstance(f, str) and not (root / f).exists():
                report["stale_ledger"].append(f)
        report["stale_ledger"].sort()

    cutoff = now - tmp_days * 86400
    for p in _files(root, ".tmp"):
        try:
            if os.lstat(p).st_mtime < cutoff:
                report["old_tmp"].append(_rel(root, p))
        except OSError:
            unreadable.add(p)
    report["old_tmp"].sort()

    report["unreadable"] = sorted(_rel(root, p) for p in unreadable)
    return report


_TITLES = {
    "unknown_dirs": "Folders that are not in the folder contract",
    "unknown_subdirs": "Subfolders that are not allowed here",
    "duplicates": "Groups of identical files",
    "stale_ledger": "Ledger entries marked done whose file is missing",
    "old_tmp": "Old files in .tmp",
    "unmoved_mcp": "Paid renders in .tmp not moved to their home yet",
    "mcp_already_home": "Copies in .tmp whose bytes already sit in their home",
    "unreadable": "Files that could not be read",
}


def format_report(report):
    lines = []
    for key in _KEYS:
        items = report.get(key) or []
        if not items:
            continue
        lines.append(f"{_TITLES[key]}: {len(items)}")
        for item in items:
            lines.append("  " + (" == ".join(item) if isinstance(item, list) else item))
    return "\n".join(lines) if lines else "clean"
