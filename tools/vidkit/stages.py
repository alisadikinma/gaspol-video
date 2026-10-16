"""Per-stage fingerprint cache: skip a step whose inputs, parameters and recipe version
have not changed and whose outputs still exist."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

CHUNK = 1024 * 1024


class StageError(RuntimeError):
    """An input file for a fingerprint is missing or unreadable."""


def _file_sha(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                h.update(chunk)
    except OSError as exc:
        raise StageError(f"cannot fingerprint {path}: {exc.strerror or exc}") from exc
    return h.hexdigest()


def _memo_sha(path, memo):
    """`_file_sha`, remembered in `memo` under (path, mtime_ns, size) so a file that changes
    between two calls is hashed again."""
    if memo is None:
        return _file_sha(path)
    try:
        st = os.stat(path)
    except OSError:
        return _file_sha(path)          # raises StageError with the real reason
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in memo:
        memo[key] = _file_sha(path)
    return memo[key]


def fingerprint(files=(), params=None, version="1", sha_memo=None):
    """sha256 over each file's content sha256 (in order), the canonical json of `params`
    and `version`. File names do not count, only bytes. `sha_memo` (a dict) lets one run
    hash a file used by many stages once."""
    h = hashlib.sha256()
    for f in files:
        h.update(_memo_sha(f, sha_memo).encode())
        h.update(b"\n")
    h.update(json.dumps(params, sort_keys=True, separators=(",", ":")).encode())
    h.update(b"\n")
    h.update(str(version).encode())
    return h.hexdigest()


class StageCache:
    """JSON file of {stage: {"fp": ..., "outputs": [...]}}. Never raises on a bad or
    unwritable cache: a bad file reads as empty, an unwritable place turns caching off
    for this run with one warning on stderr."""

    def __init__(self, path):
        self.path = Path(path)
        self.disabled = False

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def is_fresh(self, stage, fp, outputs):
        if self.disabled:
            return False
        entry = self._load().get(stage)
        if not isinstance(entry, dict) or entry.get("fp") != fp:
            return False
        return all(Path(o).is_file() for o in outputs)

    def record(self, stage, fp, outputs):
        if self.disabled:
            return
        data = self._load()
        data[stage] = {"fp": fp, "outputs": [str(o) for o in outputs]}
        self._write(data)

    def drop(self, stage):
        """Forget one stage. Called BEFORE its outputs are rewritten, so a crash mid-write
        can never leave an old fingerprint vouching for a half-written file."""
        if self.disabled:
            return
        data = self._load()
        if stage in data:
            del data[stage]
            self._write(data)

    def _write(self, data):
        tmp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # mkstemp: an unpredictable name, created O_EXCL, so a planted symlink is never followed
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name + ".",
                                       suffix=".tmp")
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(data, sort_keys=True, indent=1))
            os.replace(tmp, self.path)
        except OSError as exc:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            self.disabled = True
            print(f"warning: stage cache {self.path} not writable ({exc}); "
                  "caching disabled for this run", file=sys.stderr)
