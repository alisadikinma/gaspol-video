import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SETUP_SH = ROOT / "tools" / "setup.sh"


def _write_fake_python(path: Path, version: str):
    """A stand-in `python3` that answers `-c '<version probe code>'` with a fixed version
    line, regardless of the code passed — good enough for setup.sh's own version check,
    without needing a real old Python interpreter lying around on this machine."""
    path.write_text(f'#!/usr/bin/env bash\necho "{version}"\n', encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class SetupShPythonVersionGateTest(unittest.TestCase):
    def test_old_python_is_refused_before_any_venv_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_python = Path(tmp) / "fake-python3.8"
            _write_fake_python(fake_python, "3.8")
            gaspol_home = Path(tmp) / "gaspol-video-home"

            env = dict(os.environ)
            env["PYTHON"] = str(fake_python)
            env["GASPOL_VIDEO_HOME"] = str(gaspol_home)

            proc = subprocess.run(
                ["bash", str(SETUP_SH)], env=env, capture_output=True, text=True,
            )

            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("Python 3.10+", proc.stderr)
            self.assertIn("3.8", proc.stderr)
            self.assertIn(str(fake_python), proc.stderr)
            self.assertFalse(
                (gaspol_home / "venv").exists(),
                "a refused version check must never create a venv",
            )

    def test_new_enough_python_passes_the_gate(self):
        # This test only proves the gate itself doesn't false-positive on a fake modern
        # interpreter; it stops right after the gate (pip install would need network).
        with tempfile.TemporaryDirectory() as tmp:
            fake_python = Path(tmp) / "fake-python3.12"
            _write_fake_python(fake_python, "3.12")
            gaspol_home = Path(tmp) / "gaspol-video-home"

            env = dict(os.environ)
            env["PYTHON"] = str(fake_python)
            env["GASPOL_VIDEO_HOME"] = str(gaspol_home)

            proc = subprocess.run(
                ["bash", str(SETUP_SH)], env=env, capture_output=True, text=True, timeout=30,
            )

            # A fake python's `-m venv` will fail (it is not a real interpreter), but that
            # failure must happen AFTER the version gate passed, not because of it.
            self.assertNotIn("Python 3.10+", proc.stdout + proc.stderr)


class SetupShStaleVenvGateTest(unittest.TestCase):
    def test_existing_venv_with_old_python_is_refused_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            gaspol_home = Path(tmp) / "gaspol-video-home"
            venv_bin = gaspol_home / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            _write_fake_python(venv_bin / "python", "3.9")

            env = dict(os.environ)
            env["GASPOL_VIDEO_HOME"] = str(gaspol_home)

            proc = subprocess.run(
                ["bash", str(SETUP_SH)], env=env, capture_output=True, text=True,
            )

            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("3.9", proc.stderr)
            self.assertIn(str(gaspol_home / "venv"), proc.stderr)
            self.assertIn("delete", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
