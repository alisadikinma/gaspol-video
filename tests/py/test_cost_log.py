import contextlib
import hashlib
import io
import json
import os
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
        self.pricing = Path(self.tmp.name) / "pricing.json"
        self.set_pricing(nb2=2.0, veo=0.5)
        patcher = mock.patch.dict(os.environ, {"GASPOL_PRICING": str(self.pricing)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def set_pricing(self, nb2=None, veo=None, tts=None, music=None, sfx=None):
        def item(unit, price):
            return {"unit": unit, "price": price, "source": "test" if price is not None else ""}
        self.pricing.write_text(json.dumps({"currency": "XXX", "items": {
            "nb2-image": item("image", nb2),
            "veo-3.1-fast-clip": item("second", veo),
            "eleven-tts": item("1k-chars", tts),
            "eleven-music": item("second", music),
            "eleven-sfx": item("clip", sfx),
        }}))

    def log_path(self):
        return Path(self.proj) / "work" / "cost-log.json"


class ReportTest(Base):
    def test_priced_totals_and_failed_share(self):
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3", "--scene", "01")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1", "--scene", "01",
            "--status", "failed")
        code, out, _ = run(self.proj, "report")
        self.assertEqual(code, 0)
        self.assertIn("nb2-image", out)
        self.assertIn("4", out)
        self.assertIn("8.00", out)          # 4 units x 2.0
        self.assertIn("failed share: 25%", out)

    def test_unpriced_report_prints_units_and_no_money(self):
        self.set_pricing(nb2=None, veo=0.5)
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3")
        code, out, _ = run(self.proj, "report")
        self.assertEqual(code, 0)
        self.assertIn("UNPRICED", out)
        self.assertIn("nb2-image", out)
        self.assertIn("3", out)
        self.assertNotIn("0.00", out)
        self.assertIn("n/a", out)

    def test_empty_source_counts_as_unpriced(self):
        data = json.loads(self.pricing.read_text())
        data["items"]["nb2-image"]["source"] = ""
        data["items"]["nb2-image"]["price"] = 2.0
        self.pricing.write_text(json.dumps(data))
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3")
        _, out, _ = run(self.proj, "report")
        self.assertIn("UNPRICED", out)
        self.assertNotIn("6.00", out)

    def test_fractional_units_and_repeated_scene(self):
        for _ in range(5):
            run(self.proj, "add", "--kind", "veo-3.1-fast-clip", "--units", "1.5", "--scene", "02")
        _, out, _ = run(self.proj, "report")
        self.assertIn("7.5", out)
        self.assertIn("3.75", out)           # 7.5 x 0.5
        self.assertEqual(len(json.loads(self.log_path().read_text())["entries"]), 5)

    def test_zero_units_accepted(self):
        code, _, _ = run(self.proj, "add", "--kind", "nb2-image", "--units", "0")
        self.assertEqual(code, 0)


class AddValidationTest(Base):
    def test_bad_units_rejected(self):
        for bad in ("-1", "nan", "inf", "-inf", "abc", ""):
            code, _, err = run(self.proj, "add", "--kind", "nb2-image", "--units", bad)
            self.assertEqual(code, 2, bad)
        self.assertFalse(self.log_path().exists())

    def test_unknown_kind_names_known_kinds(self):
        code, _, err = run(self.proj, "add", "--kind", "bogus", "--units", "1")
        self.assertEqual(code, 2)
        self.assertIn("nb2-image", err)
        self.assertIn("eleven-sfx", err)
        self.assertFalse(self.log_path().exists())


class EstimateTest(Base):
    def test_estimate_priced(self):
        code, out, _ = run(self.proj, "estimate", "--plan",
                           '{"nb2-image": 10, "veo-3.1-fast-clip": 8}')
        self.assertEqual(code, 0)
        self.assertIn("24.00", out)          # 10x2 + 8x0.5

    def test_estimate_reads_plan_file(self):
        plan = Path(self.tmp.name) / "plan.json"
        plan.write_text('{"nb2-image": 1}')
        code, out, _ = run(self.proj, "estimate", "--plan", str(plan))
        self.assertEqual(code, 0)
        self.assertIn("2.00", out)

    def test_estimate_refuses_naming_every_unpriced(self):
        self.set_pricing(nb2=None, veo=None, tts=1.0)
        code, out, err = run(self.proj, "estimate", "--plan",
                             '{"nb2-image": 1, "veo-3.1-fast-clip": 2, "eleven-tts": 3}')
        self.assertEqual(code, 2)
        self.assertIn("nb2-image", err)
        self.assertIn("veo-3.1-fast-clip", err)
        self.assertNotIn("eleven-tts", err)
        self.assertEqual(out, "")

    def test_estimate_bad_plan(self):
        for bad in ("not json", '[1]', '{"nb2-image": -1}', '{"bogus": 1}', '{"nb2-image": "x"}'):
            code, _, _ = run(self.proj, "estimate", "--plan", bad)
            self.assertEqual(code, 2, bad)


class BudgetTest(Base):
    def test_no_budget(self):
        code, out, _ = run(self.proj, "check")
        self.assertEqual(code, 0)
        self.assertIn("no budget", out)

    def test_over_budget_fails(self):
        run(self.proj, "budget", "--set", "5")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3")   # 6.00
        code, out, _ = run(self.proj, "check")
        self.assertEqual(code, 1)
        self.assertIn("over budget", out)

    def test_budget_equal_to_total_passes(self):
        run(self.proj, "budget", "--set", "6")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3")
        code, _, _ = run(self.proj, "check")
        self.assertEqual(code, 0)

    def test_bad_budget_rejected(self):
        for bad in ("-1", "nan", "abc"):
            code, _, _ = run(self.proj, "budget", "--set", bad)
            self.assertEqual(code, 2, bad)

    def test_report_shows_budget(self):
        run(self.proj, "budget", "--set", "10")
        run(self.proj, "add", "--kind", "nb2-image", "--units", "3")
        _, out, _ = run(self.proj, "report")
        self.assertIn("budget: 10", out)


class StorageTest(Base):
    def test_malformed_log_not_overwritten(self):
        self.log_path().parent.mkdir(parents=True)
        self.log_path().write_text("{broken")
        before = hashlib.sha256(self.log_path().read_bytes()).hexdigest()
        for argv in (("add", "--kind", "nb2-image", "--units", "1"),
                     ("budget", "--set", "5"), ("report",), ("check",)):
            code, _, _ = run(self.proj, *argv)
            self.assertEqual(code, 2, argv)
        self.assertEqual(hashlib.sha256(self.log_path().read_bytes()).hexdigest(), before)

    def test_wrong_shape_log_exit_2(self):
        self.log_path().parent.mkdir(parents=True)
        self.log_path().write_text('{"entries": "x"}')
        code, _, _ = run(self.proj, "report")
        self.assertEqual(code, 2)

    def test_atomic_write_keeps_old_file_when_replace_fails(self):
        run(self.proj, "add", "--kind", "nb2-image", "--units", "1")
        before = self.log_path().read_bytes()
        with mock.patch("tools.cost_log.os.replace", side_effect=OSError("boom")):
            code, _, _ = run(self.proj, "add", "--kind", "nb2-image", "--units", "9")
        self.assertEqual(code, 2)
        self.assertEqual(self.log_path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
