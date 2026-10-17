import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.vidkit import ml


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WeightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        data = b"weights-bytes"
        wpatch = mock.patch.dict(ml.WEIGHTS, {"x.pt": _sha(data)})
        wpatch.start()
        self.addCleanup(wpatch.stop)
        self.data = data

    def test_absent_file_raises_with_fix(self):
        (self.home / "models").mkdir()
        with self.assertRaises(ml.MLMissing) as ctx:
            ml.weight("x.pt")
        self.assertIn("run tools/setup.sh --ml", str(ctx.exception))
        self.assertIn("x.pt", str(ctx.exception))

    def test_missing_models_dir_raises(self):
        with self.assertRaises(ml.MLMissing) as ctx:
            ml.weight("x.pt")
        self.assertIn("run tools/setup.sh --ml", str(ctx.exception))

    def test_wrong_sha_raises(self):
        models = self.home / "models"
        models.mkdir()
        (models / "x.pt").write_bytes(b"something else")
        with self.assertRaises(ml.MLMissing) as ctx:
            ml.weight("x.pt")
        self.assertIn("run tools/setup.sh --ml", str(ctx.exception))
        self.assertIn("sha256", str(ctx.exception))

    def test_empty_file_raises(self):
        models = self.home / "models"
        models.mkdir()
        (models / "x.pt").write_bytes(b"")
        with self.assertRaises(ml.MLMissing):
            ml.weight("x.pt")

    def test_correct_hash_returns_path(self):
        models = self.home / "models"
        models.mkdir()
        (models / "x.pt").write_bytes(self.data)
        self.assertEqual(ml.weight("x.pt"), models / "x.pt")

    def test_verified_hash_is_cached_until_file_changes(self):
        models = self.home / "models"
        models.mkdir()
        target = models / "x.pt"
        target.write_bytes(self.data)
        with mock.patch.object(ml, "_sha256_of", wraps=ml._sha256_of) as spy:
            ml.weight("x.pt")
            ml.weight("x.pt")
            self.assertEqual(spy.call_count, 1)
            target.write_bytes(b"changed content")
            with self.assertRaises(ml.MLMissing):
                ml.weight("x.pt")

    def test_unknown_name_raises(self):
        with self.assertRaises(ml.MLMissing) as ctx:
            ml.weight("nope.pt")
        self.assertIn("run tools/setup.sh --ml", str(ctx.exception))

    def test_real_weights_pinned(self):
        self.assertEqual(
            ml.WEIGHTS["tapnextpp_ckpt.pt"],
            "cb96a43444ccb4fbdb25d800b88c7ba196179a526e78f01b021a16b1c1eff6da",
        )
        self.assertEqual(
            ml.WEIGHTS["sam2.1_hiera_small.pt"],
            "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
        )


class PathsTest(unittest.TestCase):
    def test_paths_under_home(self):
        with mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": "/tmp/gv-ml-home"}):
            self.assertEqual(str(ml.ml_python()), "/tmp/gv-ml-home/venv-ml/bin/python")
            self.assertEqual(str(ml.models_dir()), "/tmp/gv-ml-home/models")


class DeviceTest(unittest.TestCase):
    def test_env_cpu_without_importing_torch(self):
        with mock.patch.dict(os.environ, {"GASPOL_ML_DEVICE": "cpu"}):
            with mock.patch.dict(sys.modules, {"torch": None}):
                self.assertEqual(ml.device(), "cpu")

    def test_env_mps(self):
        with mock.patch.dict(os.environ, {"GASPOL_ML_DEVICE": "mps"}):
            self.assertEqual(ml.device(), "mps")

    def test_invalid_value_raises(self):
        with mock.patch.dict(os.environ, {"GASPOL_ML_DEVICE": "cuda"}):
            with self.assertRaises(ValueError):
                ml.device()

    def test_missing_torch_raises_mlmissing(self):
        env = {k: v for k, v in os.environ.items() if k != "GASPOL_ML_DEVICE"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.dict(sys.modules, {"torch": None}):
                with self.assertRaises(ml.MLMissing) as ctx:
                    ml.device()
        self.assertIn("missing torch: run tools/setup.sh --ml", str(ctx.exception))


class RequireTest(unittest.TestCase):
    def test_returns_torch_when_importable(self):
        fake = mock.Mock()
        with mock.patch.dict(sys.modules, {"torch": fake}):
            self.assertIs(ml.require(), fake)

    def test_loop_guard_raises(self):
        with mock.patch.dict(sys.modules, {"torch": None}):
            with mock.patch.dict(os.environ, {"GASPOL_VIDEO_ML_REEXEC": "1"}):
                with self.assertRaises(ml.MLMissing) as ctx:
                    ml.require()
        self.assertIn("run tools/setup.sh --ml", str(ctx.exception))

    def test_reexecs_under_ml_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "venv-ml" / "bin" / "python"
            py.parent.mkdir(parents=True)
            py.write_text("")
            env = {k: v for k, v in os.environ.items() if k != "GASPOL_VIDEO_ML_REEXEC"}
            env["GASPOL_VIDEO_HOME"] = tmp
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.dict(sys.modules, {"torch": None}):
                    with mock.patch.object(ml.os, "execv") as ex:
                        with self.assertRaises(ml.MLMissing):
                            ml.require()
                        self.assertEqual(os.environ["GASPOL_VIDEO_ML_REEXEC"], "1")
            ex.assert_called_once()
            self.assertEqual(ex.call_args[0][0], str(py))


if __name__ == "__main__":
    unittest.main()
