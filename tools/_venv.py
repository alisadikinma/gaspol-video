#!/usr/bin/env python3
"""Dependency guard for tools that need a third-party module.

    from tools import _venv
    PIL = _venv.require("PIL")

Most tools in this repo are stdlib-only on purpose (see CLAUDE.md). A few — screen capture,
thumbnail post-processing, YouTube stats — need a real package. Rather than making every
developer's system `python3` carry Pillow/Playwright/google-api-python-client, those tools
import through here first: if the module is missing from the current interpreter, this
re-execs the same script under the dedicated venv `tools/setup.sh` builds. If the module is
still missing there, the venv is stale or was never built, and this raises with the fix.
"""

import importlib
import os
import sys
from pathlib import Path


class DependencyMissing(Exception):
    """A third-party module is not importable, in this interpreter or the dedicated venv."""


def venv_python() -> Path:
    home = Path(os.environ.get("GASPOL_VIDEO_HOME", str(Path.home() / ".gaspol-video")))
    return home / "venv" / "bin" / "python"


def require(module: str):
    try:
        return importlib.import_module(module)
    except ImportError:
        pass

    python = venv_python()
    if python.exists() and Path(sys.executable) != python:
        if os.environ.get("GASPOL_VIDEO_REEXEC") == "1":
            raise DependencyMissing(f"missing {module}: run tools/setup.sh")
        os.environ["GASPOL_VIDEO_REEXEC"] = "1"
        os.execv(str(python), [str(python)] + sys.argv)

    raise DependencyMissing(f"missing {module}: run tools/setup.sh")
