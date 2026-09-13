import os
import unittest

from tools import _venv


class VenvTest(unittest.TestCase):
    def test_require_missing_module_raises_with_setup_hint(self):
        env_before = os.environ.get("GASPOL_VIDEO_REEXEC")
        os.environ["GASPOL_VIDEO_REEXEC"] = "1"
        try:
            with self.assertRaises(_venv.DependencyMissing) as ctx:
                _venv.require("module_that_does_not_exist_gv2")
            self.assertIn("run tools/setup.sh", str(ctx.exception))
        finally:
            if env_before is None:
                os.environ.pop("GASPOL_VIDEO_REEXEC", None)
            else:
                os.environ["GASPOL_VIDEO_REEXEC"] = env_before

    def test_venv_python_honours_gaspol_video_home(self):
        home_before = os.environ.get("GASPOL_VIDEO_HOME")
        os.environ["GASPOL_VIDEO_HOME"] = "/tmp/gaspol-video-test-home"
        try:
            path = _venv.venv_python()
            self.assertEqual(str(path), "/tmp/gaspol-video-test-home/venv/bin/python")
        finally:
            if home_before is None:
                os.environ.pop("GASPOL_VIDEO_HOME", None)
            else:
                os.environ["GASPOL_VIDEO_HOME"] = home_before

    def test_require_stdlib_module_returns_it_without_reexec(self):
        import json as json_module

        module = _venv.require("json")
        self.assertIs(module, json_module)


if __name__ == "__main__":
    unittest.main()
