"""Per-stage fingerprint cache: skip a step whose inputs, parameters and recipe version
have not changed and whose outputs still exist."""
import hashlib
import json
import os
import sys
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


def fingerprint(files=(), params=None, version="1"):
    """sha256 over each file's content sha256 (in order), the canonical json of `params`
    and `version`. File names do not count, only bytes."""
    h = hashlib.sha256()
    for f in files:
        h.update(_file_sha(f).encode())
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
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, sort_keys=True, indent=1))
            os.replace(tmp, self.path)
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass
            self.disabled = True
            print(f"warning: stage cache {self.path} not writable ({exc}); "
                  "caching disabled for this run", file=sys.stderr)
