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

F13 = ROOT / "reference" / "storytelling_script_gen" / "F13_Short_Form_Timeline.md"


def tl(rows):
    head = "# A/V Script\n\n| Tahap | Detik | Video | Audio |\n|---|---|---|---|\n"
    return head + "".join(f"| {s} | {d} | v | a |\n" for s, d in rows)


GOOD = [("Hook", "0-3"), ("Foreshadow", "3-6"), ("Body", "6-50"), ("CTA", "50-54")]


class TimelineTest(unittest.TestCase):
    def test_good_timeline_has_no_problems(self):
        self.assertEqual(vc.timeline_problems(tl(GOOD)), [])

    def test_decimals_and_case_ok(self):
        rows = [("thumbnail", "0-1"), ("HOOK", "0-3.0"), ("foreshadow", "3.0-6.5"), ("Body", "6.5-50"), ("cta", "50-54.5")]
        self.assertEqual(vc.timeline_problems(tl(rows)), [])

    def test_missing_foreshadow(self):
        found = vc.timeline_problems(tl([GOOD[0], GOOD[2], GOOD[3]]))
        self.assertTrue(any("foreshadow" in p.lower() for p in found), found)

    def test_out_of_order(self):
        found = vc.timeline_problems(tl([GOOD[1], GOOD[0], GOOD[2], GOOD[3]]))
        self.assertTrue(any("order" in p.lower() for p in found), found)

    def test_hook_too_long(self):
        rows = [("Hook", "0-5"), ("Foreshadow", "5-8"), ("Body", "8-50"), ("CTA", "50-54")]
        found = vc.timeline_problems(tl(rows))
        self.assertTrue(any("hook" in p.lower() for p in found), found)

    def test_hook_within_tolerance_ok(self):
        rows = [("Hook", "0-3.9"), ("Foreshadow", "3.9-6"), ("Body", "6-50"), ("CTA", "50-54")]
        self.assertEqual(vc.timeline_problems(tl(rows)), [])

    def test_malformed_detik_names_row(self):
        found = vc.timeline_problems(tl([("Hook", "abc")] + GOOD[1:]))
        self.assertTrue(any("Hook" in p and "abc" in p for p in found), found)

    def test_unknown_stage(self):
        found = vc.timeline_problems(tl(GOOD + [("Outro", "54-55")]))
        self.assertTrue(any("Outro" in p for p in found), found)

    def test_no_columns_returns_none(self):
        self.assertIsNone(vc.timeline_problems("| a | b |\n|---|---|\n| 1 | 2 |\n"))

    def test_tolerance_from_profile(self):
        self.assertEqual(vc.timeline_tolerance(), 1.0)

    def test_audit_probe_body_cta_overrun(self):
        rows = [("Hook", "0-3"), ("Foreshadow", "3-6"), ("Body", "6-58"), ("CTA", "58-70")]
        found = " | ".join(vc.timeline_problems(tl(rows)))
        self.assertIn("Body: ends at 58", found)
        self.assertIn("CTA: lasts 12", found)
        self.assertIn("total length 70", found)

    def test_cta_not_last(self):
        rows = [("Hook", "0-3"), ("Foreshadow", "3-6"), ("Body", "6-50"), ("CTA", "50-54"), ("Body", "54-56")]
        found = vc.timeline_problems(tl(rows))
        self.assertTrue(any("CTA" in p and "last" in p for p in found), found)

    def test_cta_too_short(self):
        rows = [("Hook", "0-3"), ("Foreshadow", "3-6"), ("Body", "6-50"), ("CTA", "50-51")]
        found = vc.timeline_problems(tl(rows))
        self.assertTrue(any("CTA: lasts 1" in p for p in found), found)

    def test_max_s_param(self):
        self.assertEqual(vc.timeline_problems(tl(GOOD), max_s=60), [])
        found = vc.timeline_problems(tl(GOOD), max_s=45)
        self.assertTrue(any("total length 54" in p for p in found), found)

    def test_cli_max_s(self):
        self.assertEqual(run_timeline(tl(GOOD), ["--max-s", "60"])[0], 0)
        self.assertEqual(run_timeline(tl(GOOD), ["--max-s", "45"])[0], 1)


def run_timeline(text, extra=()):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "av-script.md"
        p.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = vc.main(["timeline", str(p), *extra])
        return code, out.getvalue() + err.getvalue()


class TimelineCliTest(unittest.TestCase):
    def test_exit_0(self):
        self.assertEqual(run_timeline(tl(GOOD))[0], 0)

    def test_exit_1(self):
        self.assertEqual(run_timeline(tl(GOOD[1:]))[0], 1)

    def test_exit_2_no_columns(self):
        self.assertEqual(run_timeline("# x\n")[0], 2)

    def test_exit_2_missing_file(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(vc.main(["timeline", "/nonexistent/av.md"]), 2)


class F13Test(unittest.TestCase):
    def test_exists_with_sources_and_tags(self):
        text = F13.read_text(encoding="utf-8")
        for needle in ("fd70ee32", "2026-10-17", "[DATA]", "[TAFSIRAN]", "F12", "9 Commandments", "F5", "F6", "@alisadikinma"):
            self.assertIn(needle, text)

    def test_every_rule_line_is_tagged(self):
        for line in F13.read_text(encoding="utf-8").splitlines():
            if line.startswith("- **Rule:"):
                self.assertTrue("[DATA]" in line or "[TAFSIRAN]" in line, line)


if __name__ == "__main__":
    unittest.main()
