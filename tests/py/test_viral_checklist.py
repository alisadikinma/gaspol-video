import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools import viral_checklist as vc

ROOT = Path(__file__).resolve().parents[2]
F12 = ROOT / "reference" / "storytelling_script_gen" / "F12_Viral_Framework.md"

LATE = ("posting", "analytics")


def block(overrides=None, drop_stage=None, drop_item=None, pad="", heading="## Viral Checklist"):
    """A checklist block with every item PASS (posting/analytics PENDING), then overrides."""
    overrides = overrides or {}
    lines = [heading, "", f"|{pad} Stage | Item | Verdict |", "|---|---|---|"]
    for stage in vc.STAGES:
        if stage == drop_stage:
            continue
        for item in vc.ITEMS[stage]:
            if item == drop_item:
                continue
            verdict = overrides.get(item, "PENDING: after publishing" if stage in LATE else "PASS")
            lines.append(f"|{pad} {stage} |{pad} {item} |{pad} {verdict} |")
    return "\n".join(lines) + "\n"


def script(blk, before_notes=False):
    head = "# A/V Script - t\n\n| Timecode | Video | Audio | Beat |\n|---|---|---|---|\n| 0:00-0:03 | a | b | Hook |\n\n"
    notes = "## Production Notes\nnotes here\n\n"
    return head + (blk + "\n" + notes if before_notes else notes + blk)


def run_check(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "av-script.md"
        p.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = vc.main(["check", str(p)])
        return code, out.getvalue() + err.getvalue()


class CheckTest(unittest.TestCase):
    def test_fully_filled_block_exits_0(self):
        code, out = run_check(script(block()))
        self.assertEqual(code, 0, out)

    def test_block_missing_exits_1(self):
        code, out = run_check(script(""))
        self.assertEqual(code, 1)
        self.assertIn("Viral Checklist", out)

    def test_missing_stage_named(self):
        code, out = run_check(script(block(drop_stage="edit")))
        self.assertEqual(code, 1)
        self.assertIn("edit", out)

    def test_missing_item_named(self):
        item = vc.ITEMS["hook"][0]
        code, out = run_check(script(block(drop_item=item)))
        self.assertEqual(code, 1)
        self.assertIn(item, out)

    def test_empty_verdict(self):
        item = vc.ITEMS["script"][0]
        code, out = run_check(script(block({item: ""})))
        self.assertEqual(code, 1)
        self.assertIn(item, out)

    def test_na_without_reason(self):
        item = vc.ITEMS["caption"][0]
        for v in ("N/A", "N/A:", "N/A:   "):
            code, out = run_check(script(block({item: v})))
            self.assertEqual(code, 1, v)
            self.assertIn(item, out)

    def test_na_with_reason_ok(self):
        item = vc.ITEMS["caption"][0]
        code, out = run_check(script(block({item: "N/A: platform has no captions"})))
        self.assertEqual(code, 0, out)

    def test_fail_cell_exit_1(self):
        item = vc.ITEMS["hook"][0]
        code, out = run_check(script(block({item: "FAIL: starts with Hi guys"})))
        self.assertEqual(code, 1)
        self.assertIn(item, out)
        self.assertIn("Hi guys", out)

    def test_pending_on_posting_with_reason_ok(self):
        item = vc.ITEMS["posting"][0]
        code, out = run_check(script(block({item: "PENDING: not posted yet"})))
        self.assertEqual(code, 0, out)

    def test_pending_without_reason_fails(self):
        item = vc.ITEMS["posting"][0]
        code, _ = run_check(script(block({item: "PENDING"})))
        self.assertEqual(code, 1)

    def test_pending_on_hook_fails(self):
        item = vc.ITEMS["hook"][0]
        code, out = run_check(script(block({item: "PENDING: later"})))
        self.assertEqual(code, 1)
        self.assertIn(item, out)

    def test_padding_and_lowercase_verdicts(self):
        item = vc.ITEMS["hook"][0]
        code, out = run_check(script(block({item: "pass"}, pad="    ")))
        self.assertEqual(code, 0, out)

    def test_backticked_item_ids_accepted(self):
        text = block()
        for stage in vc.STAGES:
            for item in vc.ITEMS[stage]:
                text = text.replace(f"| {item} |", f"| `{item}` |")
        code, out = run_check(script(text))
        self.assertEqual(code, 0, out)

    def test_block_before_and_after_production_notes(self):
        self.assertEqual(run_check(script(block(), before_notes=True))[0], 0)
        self.assertEqual(run_check(script(block(), before_notes=False))[0], 0)

    def test_two_blocks_refused(self):
        code, out = run_check(script(block()) + "\n" + block())
        self.assertEqual(code, 1)
        self.assertIn("one block only", out)

    def test_unknown_item_reported(self):
        text = block() + "| hook | made-up-item | PASS |\n"
        code, out = run_check(script(text))
        self.assertEqual(code, 1)
        self.assertIn("made-up-item", out)

    def test_every_problem_listed_at_once(self):
        a, b = vc.ITEMS["hook"][0], vc.ITEMS["script"][0]
        code, out = run_check(script(block({a: "FAIL: x", b: ""})))
        self.assertEqual(code, 1)
        self.assertIn(a, out)
        self.assertIn(b, out)

    def test_missing_file_exits_2_one_line(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = vc.main(["check", "/nonexistent/av-script.md"])
        self.assertEqual(code, 2)
        self.assertEqual(len((out.getvalue() + err.getvalue()).strip().splitlines()), 1)


class RateTest(unittest.TestCase):
    def test_all_green_percent_keys(self):
        r = vc.rate({"watchedFullPct": 21, "avgViewPct": 50.0, "views": 100001})
        self.assertEqual(r["watched_full"], "pass")
        self.assertEqual(r["avg_watch"], "pass")
        self.assertEqual(r["replicate"], "yes")

    def test_all_green_fraction_keys(self):
        r = vc.rate({"watchedFull": 0.21, "avgWatch": 0.5, "views": 100001})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("pass", "pass", "yes"))

    def test_boundaries(self):
        r = vc.rate({"watchedFullPct": 20, "avgViewPct": 50, "views": 100000})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("pass", "pass", "no"))

    def test_below_thresholds_fail(self):
        r = vc.rate({"watchedFullPct": 19.9, "avgViewPct": 49.9, "views": 5})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("fail", "fail", "no"))

    def test_missing_keys_unknown_and_named(self):
        r = vc.rate({})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("unknown",) * 3)
        joined = " ".join(r["notes"])
        for key in ("watchedFullPct", "avgViewPct", "views"):
            self.assertIn(key, joined)

    def test_none_values_unknown(self):
        r = vc.rate({"watchedFullPct": None, "avgViewPct": None, "views": None})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("unknown",) * 3)

    def test_percent_strings(self):
        r = vc.rate({"watchedFullPct": "21%", "avgViewPct": " 49% ", "views": "100,001"})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("pass", "fail", "yes"))

    def test_garbage_strings_unknown(self):
        r = vc.rate({"watchedFullPct": "lots", "avgViewPct": "n/a", "views": "many"})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("unknown",) * 3)

    def test_out_of_range_unknown_with_note(self):
        r = vc.rate({"watchedFullPct": 120, "avgViewPct": -3, "watchedFull": 1.5, "views": -1})
        self.assertEqual((r["watched_full"], r["avg_watch"], r["replicate"]), ("unknown",) * 3)
        self.assertTrue(r["notes"])

    def test_bool_is_not_a_number(self):
        self.assertEqual(vc.rate({"views": True})["replicate"], "unknown")

    def test_non_dict_unknown(self):
        self.assertEqual(vc.rate(None)["avg_watch"], "unknown")

    def test_shape_written_by_yt_stats(self):
        # Same keys and types as tools/yt_stats.fetch() writes (see tests/py/test_yt_stats.py).
        entry = {
            "videoId": "abc123",
            "title": "t",
            "publishedAt": "2026-10-01T00:00:00Z",
            "durationMin": 0.8,
            "views": 150000,
            "likes": 9000,
            "comments": 120,
            "avgViewPct": 61.4,
            "avgViewDurationS": 28.0,
            "watchTimeH": 1200.5,
            "subsGained": 40,
            "ctr": None,
            "ctr_source": "manual -- YouTube Studio only",
            "fetched_at": "2026-10-02T00:00:00Z",
        }
        r = vc.rate(entry)
        self.assertEqual(r["avg_watch"], "pass")
        self.assertEqual(r["replicate"], "yes")
        # yt_stats does not write a watched-full figure: never guessed.
        self.assertEqual(r["watched_full"], "unknown")
        self.assertIn("watchedFullPct", " ".join(r["notes"]))

    def test_rate_cli_reads_calibration(self):
        cal = {"videos": [{"videoId": "v1", "views": 200000, "avgViewPct": 55.0}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "calibration.json"
            p.write_text(json.dumps(cal), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = vc.main(["rate", str(p)])
        self.assertEqual(code, 0)
        self.assertIn("v1", out.getvalue())
        self.assertIn("pass", out.getvalue())

    def test_rate_cli_bad_json_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "calibration.json"
            p.write_text("{nope", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = vc.main(["rate", str(p)])
        self.assertEqual(code, 2)

    def test_thresholds_are_tagged_course(self):
        self.assertEqual(vc.THRESHOLDS["source"], "course")


class F12Test(unittest.TestCase):
    def test_every_item_id_in_f12(self):
        text = F12.read_text(encoding="utf-8")
        for stage in vc.STAGES:
            for item in vc.ITEMS[stage]:
                self.assertIn(f"`{item}`", text, f"{stage}/{item} missing in F12")

    def test_item_counts_3_to_5(self):
        self.assertEqual(len(vc.STAGES), 7)
        for stage in vc.STAGES:
            self.assertTrue(3 <= len(vc.ITEMS[stage]) <= 5, stage)

    def test_person_claim_guard_is_an_item(self):
        self.assertIn("person-claim-verified", vc.ITEMS["hook"])


if __name__ == "__main__":
    unittest.main()
