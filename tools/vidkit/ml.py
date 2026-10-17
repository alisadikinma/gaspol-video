"""Guard for the machine-learning tools (point tracking, segmentation).

These tools need torch, TAPNext++ and SAM 2.1. That stack is large (torch, jax, 2.4 GB of
weights) and pins its own numpy and opencv, so it lives in its own venv, `venv-ml`, built by
`tools/setup.sh --ml`. It is kept apart from the shared `venv` so Pillow, Playwright and
mediapipe tools never inherit it, and a torch upgrade never breaks them.

This module imports only the standard library. torch is imported lazily, so any tool can
ask where the weights are or which device to use before the heavy stack is loaded.
"""

import hashlib
import importlib
import os
import sys
from pathlib import Path

FIX = "run tools/setup.sh --ml"

WEIGHTS = {
    "tapnextpp_ckpt.pt": "cb96a43444ccb4fbdb25d800b88c7ba196179a526e78f01b021a16b1c1eff6da",
    "sam2.1_hiera_small.pt": "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
}

_verified = {}


class MLMissing(RuntimeError):
    """The ML venv, a model weight or torch is missing. The message names the fix."""


def _home() -> Path:
    return Path(os.environ.get("GASPOL_VIDEO_HOME", str(Path.home() / ".gaspol-video")))


def ml_python() -> Path:
    return _home() / "venv-ml" / "bin" / "python"


def models_dir() -> Path:
    return _home() / "models"


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weight(name: str) -> Path:
    expected = WEIGHTS.get(name)
    if expected is None:
        raise MLMissing(f"missing weight {name} (unknown name): {FIX}")
    path = models_dir() / name
    if not path.is_file():
        raise MLMissing(f"missing weight {path}: {FIX}")
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if _verified.get(key) == expected:
        return path
    got = _sha256_of(path)
    if got != expected:
        raise MLMissing(f"weight {path} has wrong sha256 {got} (expected {expected}): {FIX}")
    _verified[key] = expected
    return path


def device() -> str:
    forced = os.environ.get("GASPOL_ML_DEVICE")
    if forced is not None:
        if forced not in ("cpu", "mps"):
            raise ValueError(f"GASPOL_ML_DEVICE must be cpu or mps, got {forced!r}")
        return forced
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        raise MLMissing(f"missing torch: {FIX}") from None
    return "mps" if torch.backends.mps.is_available() else "cpu"


def reexec_argv(python, argv=None):
    """argv that re-runs the current command under `python`.

    A `python -m pkg` run keeps `-m pkg`: `sys.argv[0]` is then the path of `__main__.py`, and
    running that path as a plain script breaks its relative imports.
    """
    argv = list(sys.argv if argv is None else argv)
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    name = getattr(spec, "name", None)
    if name:
        if name.endswith(".__main__"):
            name = name[: -len(".__main__")]
        return [str(python), "-m", name, *argv[1:]]
    return [str(python), *argv]


def require():
    """Return torch; when this interpreter lacks it, re-exec the script under venv-ml."""
    try:
        return importlib.import_module("torch")
    except ImportError:
        pass

    python = ml_python()
    if python.exists() and Path(sys.executable) != python:
        if os.environ.get("GASPOL_VIDEO_ML_REEXEC") == "1":
            raise MLMissing(f"missing torch: {FIX}")
        os.environ["GASPOL_VIDEO_ML_REEXEC"] = "1"
        os.execv(str(python), reexec_argv(python))

    raise MLMissing(f"missing torch: {FIX}")
