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


class SetupShMlFlagTest(unittest.TestCase):
    def setUp(self):
        self.text = SETUP_SH.read_text(encoding="utf-8")

    def test_ml_flag_is_parsed(self):
        self.assertIn("--ml)", self.text)
        self.assertIn("WITH_ML", self.text)

    def test_weights_urls_and_hashes_pinned(self):
        for needle in (
            "https://storage.googleapis.com/dm-tapnet/tapnextpp/tapnextpp_ckpt.pt",
            "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
            "cb96a43444ccb4fbdb25d800b88c7ba196179a526e78f01b021a16b1c1eff6da",
            "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
        ):
            self.assertIn(needle, self.text)

    def test_sam2_cuda_build_disabled(self):
        self.assertIn("SAM2_BUILD_CUDA=0", self.text)

    def test_requirements_pin_git_commits(self):
        req = (ROOT / "requirements-ml.txt").read_text(encoding="utf-8")
        self.assertIn("tapnet[torch] @ git+https://github.com/google-deepmind/tapnet.git@", req)
        self.assertIn("SAM-2 @ git+https://github.com/facebookresearch/sam2.git@", req)
        self.assertIn("einops==", req)

    def _fetch_pinned_body(self):
        start = self.text.index("fetch_pinned() {")
        return self.text[start:self.text.index("\n  }\n", start)]

    def test_download_has_timeouts_and_retries(self):
        body = self._fetch_pinned_body()
        for flag in ("--connect-timeout 30", "--speed-time 60", "--speed-limit 1024", "--retry 3"):
            self.assertIn(flag, body)

    def test_partial_download_removed_on_failure_or_interrupt(self):
        body = self._fetch_pinned_body()
        self.assertIn("trap", body)
        self.assertIn('rm -f "$tmp"', body)
        for sig in ("EXIT", "INT", "TERM"):
            self.assertIn(sig, body)

    def test_interrupted_download_leaves_no_temp_file(self):
        # Run the real function against a stub curl that writes bytes and then dies.
        start = self.text.index("  fetch_pinned() {")
        func = self.text[start:self.text.index("\n  }\n", start) + 5]
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            curl = bindir / "curl"
            curl.write_text('#!/usr/bin/env bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done\n'
                            'echo partial > "$out"\nkill -TERM $PPID\nsleep 2\n', encoding="utf-8")
            curl.chmod(0o755)
            models = Path(tmp) / "models"
            models.mkdir()
            script = f'MODEL_DIR="{models}"\n{func}\nfetch_pinned "{models}/w.pt" http://x/w.pt deadbeef\n'
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
            subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(sorted(p.name for p in models.iterdir()), [])

    def test_unknown_option_refused(self):
        proc = subprocess.run(
            ["bash", str(SETUP_SH), "--bogus"], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--ml", proc.stderr)


if __name__ == "__main__":
    unittest.main()
