"""Scan a project folder against the folder contract, and clean what the scan finds.

``scan`` reports stray folders and subfolders, duplicate files, stale ledger entries, old
``.tmp`` files and MCP renders that were not moved home. It never writes.
``apply_unknown_dirs`` moves stray folders into ``_arsip/``. ``empty_tmp`` is the only deletion
and it stays inside ``.tmp/``; it keeps every file in the MCP area (``.tmp/image``,
``.tmp/video``, any letter case) and the paid TTS cache ``.tmp/vocache-*`` unless the file is
verified at delete time to be a byte-identical copy of a file already at home.
"""
import hashlib
import os
import time
from pathlib import Path

from tools import renders

CONTRACT_DIRS = {"ref", "keyframes", "shots", "clips", "vo", "sfx", "work", "output", "_arsip",
                 ".tmp", "screens", "packaging"}
DUP_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "output", "_arsip")
FLAT_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "_arsip")
# Subfolders the plugin's own tools create inside a contract folder. Keep this list explicit:
# a name is added only with the tool that makes it.
ALLOWED_SUBDIRS = {
    "output": {"stems"},    # tools/make_stems.py writes output/stems/{voice,sfx,music}.wav
    "ref": {"sumber"},      # vidkit ingest / vidkit scenes (skills/video-repackage): ref/sumber, ref/sumber/scenes
    "vo": {"native",        # tools/vidkit/js/cast_voice.mjs default out: vo/native/<scene>.mp3
           "master"},       # tools/check_vo_duration.py convention: vo/master/scene-NN-narr.mp3
}
# Pre-v3.3.0 MCP scratch folder. It can hold paid renders, so it is reported like any stray folder.
LEGACY_SCRATCH = ".render-tmp"
ARCHIVED_PREFIX = "folder-"

_KEYS = ("unknown_dirs", "unknown_subdirs", "duplicates", "stale_ledger", "old_tmp",
         "unmoved_mcp", "mcp_already_home", "unreadable")


def _check_project(project):
    root = Path(project)
    if not root.is_dir():
        raise ValueError(f"not a directory: {project}")
    if (root / ".tmp").is_symlink():
        raise ValueError(f".tmp is a symlink: {root / '.tmp'}")
    return root


def _entries(path, unreadable=None):
    try:
        with os.scandir(path) as it:
            return sorted(it, key=lambda e: e.name)
    except OSError:
        if unreadable is not None:
            unreadable.add(str(path))
        return []


def _rel(root, path):
    return Path(path).relative_to(root).as_posix()


def _files(root, rel_dir, unreadable=None):
    """Regular files (no symlinks, no symlinked dirs) below root/rel_dir, sorted.

    A directory that cannot be listed is added to ``unreadable`` (when given)."""
    out = []
    start = root / rel_dir
    if start.is_symlink() or not start.is_dir():
        return out

    def onerror(exc):
        if unreadable is not None and getattr(exc, "filename", None):
            unreadable.add(str(exc.filename))
    for dp, dn, fn in os.walk(start, followlinks=False, onerror=onerror):
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


def _is_mcp_area(rel):
    """True when the first component under ``.tmp/`` is ``image`` or ``video`` (any case)."""
    parts = Path(rel).parts
    return len(parts) >= 2 and parts[0] == ".tmp" and parts[1].lower() in ("image", "video")


class _HomeFiles:
    """Home files by size, listed (stat only) on first use. Nothing is hashed here."""

    def __init__(self, root):
        self._root = root
        self._by_size = None

    def same_size(self, size):
        if self._by_size is None:
            self._by_size = {}
            for d in DUP_DIRS:
                for p in _files(self._root, d):
                    try:
                        n = os.stat(p).st_size
                    except OSError:
                        continue
                    if n:
                        self._by_size.setdefault(n, []).append(p)
        return self._by_size.get(size, ())


def scan(project, tmp_days=7, now=None):
    root = _check_project(project)
    now = time.time() if now is None else now
    report = {k: [] for k in _KEYS}
    unreadable = set()

    for e in _entries(root, unreadable):
        if e.name.lower() in CONTRACT_DIRS:
            continue
        if e.name.startswith(".") and e.name != LEGACY_SCRATCH:
            continue
        if e.is_dir(follow_symlinks=False) or (e.is_symlink() and e.is_dir()):
            report["unknown_dirs"].append(e.name)

    subdir_roots = tuple(dict.fromkeys(
        [x for x in FLAT_DIRS if x != "_arsip"] + list(ALLOWED_SUBDIRS)))
    for d in subdir_roots:
        base = root / d
        if base.is_symlink() or not base.is_dir():
            continue
        allowed = ALLOWED_SUBDIRS.get(d, set())
        for e in _entries(base, unreadable):
            if e.name in allowed:
                continue
            if e.is_dir(follow_symlinks=False) or (e.is_symlink() and e.is_dir()):
                report["unknown_subdirs"].append(f"{d}/{e.name}")
    report["unknown_subdirs"].sort()

    home = []
    for d in DUP_DIRS:
        home.extend(_files(root, d, unreadable))
    mcp = [p for p in _files(root, ".tmp", unreadable) if _is_mcp_area(_rel(root, p))]
    groups = _hash_groups(home + mcp, unreadable)
    home_set = set(home)
    stray = tuple(u + "/" for u in report["unknown_subdirs"])
    for paths in groups.values():
        in_home = sorted(_rel(root, p) for p in paths if p in home_set)
        in_mcp = sorted(_rel(root, p) for p in paths if p not in home_set)
        if len(in_home) >= 2:
            report["duplicates"].append(in_home)
        if in_home:
            clean = [h for h in in_home if not h.startswith("_arsip/") and not h.startswith(stray)]
            pick = (clean or in_home)[0]
            for m in in_mcp:
                report["mcp_already_home"].append(f"{m} = {pick}")
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
    for p in _files(root, ".tmp", unreadable):
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


class Moved(list):
    """List of ``(src, dst)`` pairs; ``failed`` holds ``(path, error)`` for moves that did not happen."""

    def __init__(self, *a):
        super().__init__(*a)
        self.failed = []


def apply_unknown_dirs(project, report):
    """Move stray folders to ``_arsip/folder-X`` or ``_arsip/folder-P-X``.

    Returns a list of ``(src, dst)`` pairs with a ``.failed`` list of ``(path, error)``.
    One failed move does not stop the others. Nothing inside ``_arsip/`` is touched."""
    root = _check_project(project)
    entries = list(report.get("unknown_dirs", [])) + list(report.get("unknown_subdirs", []))
    entries = [e for e in entries if os.path.lexists(root / e)]
    moved = Moved()
    if not entries:
        return moved
    arsip = root / "_arsip"
    if arsip.is_symlink():
        raise ValueError(f"_arsip is a symlink: {arsip}")
    arsip.mkdir(exist_ok=True)
    for rel in entries:
        base = ARCHIVED_PREFIX + rel.replace("/", "-")
        dst, n = arsip / base, 1
        while os.path.lexists(dst):
            n += 1
            dst = arsip / f"{base}-{n}"
        try:
            os.replace(root / rel, dst)
        except OSError as exc:
            moved.failed.append((rel, str(exc)))
            continue
        moved.append((rel, _rel(root, dst)))
    return moved


def _verified_home(path, home):
    """Home path holding exactly the bytes of ``path``, checked now, or None.

    Only home files of the same size are opened and hashed."""
    try:
        size = os.stat(path).st_size
        if size == 0:
            return None
        digest = _sha256(path)
    except OSError:
        return None
    for cand in sorted(home.same_size(size), key=lambda c: (_rel_arsip(c), c)):
        try:
            if os.path.islink(cand) or os.stat(cand).st_size != size or _sha256(cand) != digest:
                continue
        except OSError:
            continue
        try:
            if _sha256(path) != digest:   # the .tmp file changed while the home was checked
                return None
        except OSError:
            return None
        return cand
    return None


def _rel_arsip(cand):
    return "/_arsip/" in cand.replace(os.sep, "/")


def empty_tmp(project, include_mcp=False):
    """Delete the content of ``.tmp/``.

    Kept unless ``include_mcp``: every file in the MCP area (``.tmp/image``, ``.tmp/video``,
    any letter case) that is not, at delete time, re-verified as a byte-identical copy of a
    file in a home folder. ``.tmp/vocache-*`` (paid TTS cache) is always kept.

    Returns ``{"deleted", "kept_mcp", "kept_tts", "home_of", "failed"}``; ``failed`` is a list
    of ``(path, error)``. One failure does not stop the rest.
    """
    root = _check_project(project)
    tmp = root / ".tmp"
    result = {"deleted": [], "kept_mcp": [], "kept_tts": [], "home_of": {}, "failed": []}
    if not tmp.is_dir():
        return result
    root_real = os.path.realpath(root)
    tmp_real = os.path.realpath(tmp)
    if os.path.dirname(tmp_real) != root_real:
        raise ValueError(f".tmp resolves outside the project: {tmp_real}")
    home = _HomeFiles(root)

    def inside(path):
        return os.path.commonpath([tmp_real, path]) == tmp_real and path != tmp_real

    blocked = set()

    def block(dp):
        while dp != tmp_real and dp not in blocked:
            blocked.add(dp)
            dp = os.path.dirname(dp)

    def walk_error(exc):
        name = getattr(exc, "filename", None)
        if name:
            result["failed"].append((Path(os.path.relpath(name, root_real)).as_posix(), str(exc)))
            block(str(name))

    for dp, dn, fn in os.walk(tmp_real, topdown=False, followlinks=False, onerror=walk_error):
        for name in fn + [d for d in dn if os.path.islink(os.path.join(dp, d))]:
            path = os.path.join(dp, name)
            rel = Path(os.path.relpath(path, root_real)).as_posix()
            if not inside(path):
                continue
            is_link = os.path.islink(path)
            if not is_link and name.startswith("vocache-"):
                result["kept_tts"].append(rel)
                block(dp)
                continue
            if not is_link and not include_mcp and _is_mcp_area(rel):
                found = _verified_home(path, home)
                if found is None:
                    result["kept_mcp"].append(rel)
                    block(dp)
                    continue
                home_rel = Path(os.path.relpath(found, str(root))).as_posix()
                try:
                    os.unlink(path)
                except OSError as exc:
                    result["failed"].append((rel, str(exc)))
                    block(dp)
                    continue
                result["deleted"].append(rel)
                result["home_of"][rel] = home_rel
                continue
            try:
                os.unlink(path)
            except OSError as exc:
                result["failed"].append((rel, str(exc)))
                block(dp)
                continue
            result["deleted"].append(rel)
        for name in dn:
            path = os.path.join(dp, name)
            if os.path.islink(path) or not inside(path) or path in blocked:
                continue
            try:
                os.rmdir(path)
            except OSError as exc:
                result["failed"].append((Path(os.path.relpath(path, root_real)).as_posix(), str(exc)))
                block(path)
    for k in ("deleted", "kept_mcp", "kept_tts"):
        result[k].sort()
    result["failed"].sort()
    return result
