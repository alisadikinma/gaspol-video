import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import cost_log


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cost_log.main(list(argv))
        except SystemExit as exc:   # argparse usage errors exit 2
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = str(Path(self.tmp.name) / "proj")
        Path(self.proj).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def log_path(self):
        return Path(self.proj) / "work" / "cost-log.json"


class ReportTest(Base):
    def test_per_kind_units_entries_and_failed_share(self):
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3", "--scene", "01")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1", "--scene", "01",
            "--status", "failed")
        run(self.proj, "add", "--kind", "veo-3.1-fast-clip", "--units", "8", "--scene", "02")
        code, out, _ = run(self.proj, "report")
        self.assertEqual(code, 0)
        self.assertIn("nb2-image: 4 image, failed 25%", out)
        self.assertIn("veo-3.1-fast-clip: 8 second, failed 0%", out)
        self.assertIn("entries: 3", out)
        self.assertIn("failed share: 8%", out)      # 1 of 12 units
        self.assertNotRegex(out.lower(), r"price|total|budget|unpriced")

    def test_rerolls_per_scene(self):
        for _ in range(2):
            run(self.proj, "add", "--kind", "nb2-image", "--units", "1", "--scene", "05",
                "--status", "failed")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1", "--scene", "05")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1", "--scene", "06")
        _, out, _ = run(self.proj, "report")
        self.assertIn("re-rolls scene 05: 2", out)
        self.assertNotIn("scene 06", out)

    def test_empty_report(self):
        code, out, _ = run(self.proj, "report")
        self.assertEqual(code, 0)
        self.assertIn("entries: 0", out)
        self.assertIn("failed share: 0%", out)

    def test_fractional_units_and_repeated_scene(self):
        for _ in range(5):
            run(self.proj, "add", "--kind", "veo-3.1-fast-clip", "--units", "1.5", "--scene", "02")
        _, out, _ = run(self.proj, "report")
        self.assertIn("veo-3.1-fast-clip: 7.5 second", out)
        self.assertEqual(len(json.loads(self.log_path().read_text())["entries"]), 5)

    def test_zero_units_accepted(self):
        code, _, _ = run(self.proj, "add", "--kind", "nb2-image", "--units", "0")
        self.assertEqual(code, 0)


class AddValidationTest(Base):
    def test_bad_units_rejected(self):
        for bad in ("-1", "nan", "inf", "-inf", "abc", ""):
            code, _, _ = run(self.proj, "add", "--kind", "nb2-image", "--units", bad)
            self.assertEqual(code, 2, bad)
        self.assertFalse(self.log_path().exists())

    def test_unknown_kind_names_known_kinds(self):
        code, _, err = run(self.proj, "add", "--kind", "bogus", "--units", "1")
        self.assertEqual(code, 2)
        for kind in ("nb2-image", "veo-3.1-fast-clip", "eleven-tts", "eleven-music", "eleven-sfx"):
            self.assertIn(kind, err)
        self.assertFalse(self.log_path().exists())

    def test_removed_subcommands_are_gone(self):
        for cmd in ("estimate", "budget", "check"):
            code, _, _ = run(self.proj, cmd)
            self.assertEqual(code, 2, cmd)


class StorageTest(Base):
    def test_malformed_log_not_overwritten(self):
        self.log_path().parent.mkdir(parents=True)
        self.log_path().write_text("{broken")
        before = hashlib.sha256(self.log_path().read_bytes()).hexdigest()
        for argv in (("add", "--kind", "nb2-image", "--units", "1"), ("report",)):
            code, _, _ = run(self.proj, *argv)
            self.assertEqual(code, 2, argv)
        self.assertEqual(hashlib.sha256(self.log_path().read_bytes()).hexdigest(), before)

    def test_wrong_shape_log_exit_2(self):
        self.log_path().parent.mkdir(parents=True)
        self.log_path().write_text('{"entries": "x"}')
        code, _, _ = run(self.proj, "report")
        self.assertEqual(code, 2)

    def test_old_log_with_budget_key_loads_and_key_dropped_on_write(self):
        self.log_path().parent.mkdir(parents=True)
        self.log_path().write_text(json.dumps({"budget": 5, "entries": [
            {"ts": "t", "kind": "nb2-image", "units": 2, "status": "ok"}]}))
        code, out, _ = run(self.proj, "report")
        self.assertEqual(code, 0)
        self.assertIn("nb2-image: 2 image", out)
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1")
        data = json.loads(self.log_path().read_text())
        self.assertNotIn("budget", data)
        self.assertEqual(len(data["entries"]), 2)

    def test_atomic_write_keeps_old_file_when_replace_fails(self):
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1")
        before = self.log_path().read_bytes()
        with mock.patch("tools.cost_log.os.replace", side_effect=OSError("boom")):
            code, _, _ = run(self.proj, "add", "--kind", "nb2-image", "--units", "9")
        self.assertEqual(code, 2)
        self.assertEqual(self.log_path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
