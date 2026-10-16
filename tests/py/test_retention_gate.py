import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.py import media
from tools import retention_gate as rg

CANNED_NONE = "[Parsed_freezedetect_0 @ 0x1] frame info\nvideo:10kB audio:0kB\n"
CANNED_TWO = (
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 1.5\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 3.2\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 4.7\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 6\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 3\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 9\n"
)
CANNED_OPEN = "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 7.25\n"


def make_master(path, still_s, lead_s=2.0, tail_s=2.0, size="320x240"):
    """moving bars, then a flat colour held for still_s, then moving bars again."""
    parts = [("testsrc=size=%s:rate=30:duration=%s" % (size, lead_s)),
             ("color=c=red:size=%s:rate=30:duration=%s" % (size, still_s)),
             ("testsrc=size=%s:rate=30:duration=%s" % (size, tail_s))]
    args = [media.FFMPEG, "-y", "-v", "error"]
    for p in parts:
        args += ["-f", "lavfi", "-i", p]
    args += ["-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    media._run(args)
    return str(path)


class ParseFreezesTest(unittest.TestCase):
    def test_no_freezes(self):
        self.assertEqual(rg.parse_freezes(CANNED_NONE, 10.0), [])

    def test_two_freezes(self):
        self.assertEqual(rg.parse_freezes(CANNED_TWO, 10.0),
                         [(1.5, 4.7, 3.2), (6.0, 9.0, 3.0)])

    def test_freeze_running_to_end_of_file_without_freeze_end(self):
        self.assertEqual(rg.parse_freezes(CANNED_OPEN, 10.0), [(7.25, 10.0, 2.75)])


class StaticFrameTest(unittest.TestCase):
    @media.requires_ffmpeg
    def test_four_second_still_is_a_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = make_master(Path(tmp) / "m.mp4", 4.0)
            row = rg.check_static(master, 3.0)
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("1 freeze", row["numbers"])

    @media.requires_ffmpeg
    def test_two_and_a_half_second_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = make_master(Path(tmp) / "m.mp4", 2.5)
            row = rg.check_static(master, 3.0)
        self.assertEqual(row["status"], "PASS")

    @media.requires_ffmpeg
    def test_override_static_max_s_turns_the_same_cut_into_a_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = make_master(Path(tmp) / "m.mp4", 2.5)
            row = rg.check_static(master, 2.0)
        self.assertEqual(row["status"], "FAIL")

    def test_freeze_of_exactly_the_limit_is_a_fail_not_a_pass(self):
        # limit is inclusive: a 3.0 s freeze fails (>= limit)
        row = rg.static_row([(6.0, 9.0, 3.0)], 3.0)
        self.assertEqual(row["status"], "FAIL")

    def test_just_under_the_limit_passes(self):
        self.assertEqual(rg.static_row([(6.0, 8.9, 2.9)], 3.0)["status"], "PASS")


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def manifest(*items):
    return json.dumps({"items": [dict(id="i%d" % k, **it) for k, it in enumerate(items)]})


def word(text, a_ms, b_ms):
    return {"text": text, "start_ms": a_ms, "end_ms": b_ms}


class HookTest(unittest.TestCase):
    def project(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        if text is not None:
            write(Path(d.name) / "vo" / "vo-manifest.json", text)
        return Path(d.name)

    def hook(self, text, limit=3.0, words_file=None):
        project = self.project(text)
        words, why = rg.load_words(project, words_file)
        return rg.hook_row(words, why, limit)

    def test_first_word_at_2_9_passes(self):
        m = manifest(dict(words=[word("a", 2900, 3200)]))
        self.assertEqual(self.hook(m)["status"], "PASS")

    def test_first_word_at_3_1_fails(self):
        m = manifest(dict(words=[word("a", 3100, 3400)]))
        self.assertEqual(self.hook(m)["status"], "FAIL")

    def test_no_manifest_is_not_measured(self):
        self.assertEqual(self.hook(None)["status"], "not measured")

    def test_manifest_with_empty_words_is_not_measured(self):
        self.assertEqual(self.hook(manifest(dict(words=[])))["status"], "not measured")

    def test_two_items_without_film_offsets_is_not_measured(self):
        m = manifest(dict(words=[word("a", 0, 200)]), dict(words=[word("b", 0, 200)]))
        row = self.hook(m)
        self.assertEqual(row["status"], "not measured")
        self.assertIn("offset", row["numbers"])

    def test_item_offset_at_s_moves_the_first_word(self):
        m = manifest(dict(at_s=5.0, words=[word("a", 100, 300)]),
                     dict(at_s=0.5, words=[word("b", 400, 600)]))
        row = self.hook(m)
        self.assertEqual(row["status"], "PASS")
        self.assertIn("0.90", row["numbers"])

    def test_words_file_overrides_when_no_manifest(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        wf = write(Path(d.name) / "w.json", json.dumps([{"word": "x", "start": 4.0, "end": 4.2}]))
        words, why = rg.load_words(Path(d.name), str(wf))
        self.assertEqual(rg.hook_row(words, why, 3.0)["status"], "FAIL")

    def test_limit_override(self):
        m = manifest(dict(words=[word("a", 2900, 3200)]))
        self.assertEqual(self.hook(m, limit=2.0)["status"], "FAIL")


def av(*rows, header="| Timecode | Video | Audio | Beat |"):
    return "# Script\n\n%s\n|---|---|---|---|\n%s\n" % (header, "\n".join(rows))


class ForeshadowTest(unittest.TestCase):
    def fs(self, text, lo=3.0, hi=6.0):
        return rg.foreshadow_row(text, (lo, hi))

    def test_foreshadow_at_4_passes(self):
        self.assertEqual(self.fs(av("| 0:04-0:06 | v | a | Foreshadow |"))["status"], "PASS")

    def test_foreshadow_at_7_fails(self):
        self.assertEqual(self.fs(av("| 0:07-0:09 | v | a | Foreshadow |"))["status"], "FAIL")

    def test_no_foreshadow_row_fails(self):
        row = self.fs(av("| 0:00-0:03 | v | a | Hook |"))
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("no Foreshadow beat", row["numbers"])

    def test_fractional_timecode_passes(self):
        self.assertEqual(self.fs(av("| 0:03.5-0:06 | v | a | Foreshadow |"))["status"], "PASS")

    def test_garbage_timecode_is_not_measured_and_quotes_the_cell(self):
        row = self.fs(av("| soon-ish | v | a | Foreshadow |"))
        self.assertEqual(row["status"], "not measured")
        self.assertIn("soon-ish", row["numbers"])

    def test_beat_label_case_and_spacing(self):
        self.assertEqual(self.fs(av("| 0:05 | v | a |   FORESHADOW  |"))["status"], "PASS")
        self.assertEqual(self.fs(av("| 0:05 | v | a | **foreshadow** |"))["status"], "PASS")

    def test_beat_column_found_by_header_not_position(self):
        text = av("| 0:05 | Foreshadow | a | Hook |", header="| Timecode | Video | Audio | Beat |")
        self.assertEqual(self.fs(text)["status"], "FAIL")

    def test_window_override(self):
        self.assertEqual(self.fs(av("| 0:04 | v | a | Foreshadow |"), 5.0, 8.0)["status"], "FAIL")


def make_project(tmp, broll_ids=("b1",)):
    """project with a main take, one shot per id, a 6 s master and an edit plan."""
    project = Path(tmp)
    (project / "clips").mkdir()
    (project / "work").mkdir()
    media.make_clip(project / "clips" / "main.mp4", seconds=3.0)
    segments = [dict(kind="clip", src="clips/main.mp4", in_s=0.0, out_s=2.0)]
    for bid in broll_ids:
        media.make_clip(project / "clips" / (bid + ".mp4"), seconds=3.0, audio=False)
        segments.append(dict(id=bid, kind="shot", src="clips/%s.mp4" % bid, in_s=0.0, out_s=2.0))
    write(project / "work" / "edit-plan.json", json.dumps({"segments": segments}))
    master = media.make_clip(project / "master.mp4", seconds=2.0 * len(segments))
    return project, master


class BrollTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def build(self, project, master, words=None):
        plan = rg.load_plan(project)
        return rg.build_qa(project, master, plan, words)

    def set_cell(self, project, cell):
        qa = project / "work" / "retention-qa.md"
        text = qa.read_text(encoding="utf-8")
        qa.write_text(text.replace("| Picture matches the spoken words | |",
                                   "| Picture matches the spoken words | %s |" % cell), encoding="utf-8")

    @media.requires_ffmpeg
    def test_shot_segments_are_broll_main_take_is_not(self):
        project, _ = make_project(self.tmp.name, ("b1", "b2"))
        segs = rg.broll_segments(rg.load_plan(project))
        self.assertEqual([s["id"] for s in segs], ["b1", "b2"])
        self.assertEqual([(s["start"], s["end"]) for s in segs], [(2.0, 4.0), (4.0, 6.0)])

    def test_role_broll_clip_segment_counts_too(self):
        plan = {"segments": [dict(kind="clip", src="a.mp4", in_s=0, out_s=1),
                             dict(kind="clip", src="b.mp4", in_s=0, out_s=1, role="b-roll")]}
        segs = rg.broll_segments(plan)
        self.assertEqual([s["id"] for s in segs], ["seg-02"])

    def test_pad_end_counts_towards_the_timeline(self):
        plan = {"segments": [dict(kind="clip", src="a.mp4", in_s=0, out_s=1, pad_end_s=0.5),
                             dict(kind="shot", src="b.mp4", in_s=0, out_s=1)]}
        self.assertEqual(rg.broll_segments(plan)[0]["start"], 1.5)

    def test_empty_segment_list_has_no_broll(self):
        self.assertEqual(rg.broll_segments({"segments": []}), [])

    @media.requires_ffmpeg
    def test_section_written_with_range_words_sheet_and_empty_cell(self):
        project, master = make_project(self.tmp.name)
        words = [("harga", 2.1, 2.5), ("naik", 2.6, 3.0), ("lain", 5.0, 5.2)]
        self.build(project, master, words)
        text = (project / "work" / "retention-qa.md").read_text(encoding="utf-8")
        self.assertIn("## Segment b1", text)
        self.assertIn("2.00-4.00", text)
        self.assertIn("harga naik", text)
        self.assertNotIn("lain", text)
        self.assertTrue((project / ".tmp" / "retention-seg-b1.jpg").is_file())
        self.assertIn("| Picture matches the spoken words | |", text)

    @media.requires_ffmpeg
    def test_verdict_survives_rerun_when_clip_unchanged(self):
        project, master = make_project(self.tmp.name)
        self.build(project, master)
        self.set_cell(project, "PASS")
        self.build(project, master)
        text = (project / "work" / "retention-qa.md").read_text(encoding="utf-8")
        self.assertIn("| Picture matches the spoken words | PASS |", text)

    @media.requires_ffmpeg
    def test_verdict_cleared_when_clip_bytes_change(self):
        project, master = make_project(self.tmp.name)
        self.build(project, master)
        self.set_cell(project, "PASS")
        media.make_clip(project / "clips" / "b1.mp4", seconds=3.0, audio=False, size="160x120")
        self.build(project, master)
        text = (project / "work" / "retention-qa.md").read_text(encoding="utf-8")
        self.assertIn("| Picture matches the spoken words | |", text)
        self.assertIn("changed since last judged", text)

    @media.requires_ffmpeg
    def test_check_exits_1_on_empty_cell_and_0_on_pass_or_unsure(self):
        project, master = make_project(self.tmp.name)
        self.build(project, master)
        plan = rg.load_plan(project)
        problems, _ = rg.check_qa(project, plan)
        self.assertTrue(any("b1" in p and "no verdict" in p for p in problems))
        self.set_cell(project, "PASS")
        self.assertEqual(rg.check_qa(project, plan)[0], [])
        self.set_cell(project, "x")  # no-op: cell is already PASS
        qa = project / "work" / "retention-qa.md"
        qa.write_text(qa.read_text().replace("| PASS |", "| UNSURE: dark frame |"), encoding="utf-8")
        problems, notes = rg.check_qa(project, plan)
        self.assertEqual(problems, [])
        self.assertTrue(any("dark frame" in n for n in notes))

    @media.requires_ffmpeg
    def test_check_fails_on_fail_cell_and_on_missing_section(self):
        project, master = make_project(self.tmp.name)
        self.build(project, master)
        self.set_cell(project, "FAIL: shows a truck, words say invoice")
        plan = rg.load_plan(project)
        problems, _ = rg.check_qa(project, plan)
        self.assertTrue(any("shows a truck" in p for p in problems))
        (project / "work" / "retention-qa.md").unlink()
        problems, _ = rg.check_qa(project, plan)
        self.assertTrue(any("no section" in p for p in problems))

    @media.requires_ffmpeg
    def test_check_fails_when_judged_against_different_bytes(self):
        project, master = make_project(self.tmp.name)
        self.build(project, master)
        self.set_cell(project, "PASS")
        media.make_clip(project / "clips" / "b1.mp4", seconds=3.0, audio=False, size="160x120")
        problems, _ = rg.check_qa(project, rg.load_plan(project))
        self.assertTrue(any("different clip" in p for p in problems))

    def test_missing_edit_plan_is_none_and_malformed_raises(self):
        project = Path(self.tmp.name)
        self.assertIsNone(rg.load_plan(project))
        write(project / "work" / "edit-plan.json", "{not json")
        with self.assertRaises(rg.GateError):
            rg.load_plan(project)
        write(project / "work" / "edit-plan.json", json.dumps({"segments": [{"kind": "shot"}]}))
        with self.assertRaises(rg.GateError):
            rg.load_plan(project)


def make_stem(path, volume_db, active_s=4.0, total_s=4.0, freq=440):
    """mono wav: a sine at volume_db for active_s, silence up to total_s."""
    media._run([media.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=%d:duration=%s" % (freq, active_s), "-af",
                "volume=%sdB,apad=whole_dur=%s" % (volume_db, total_s), "-ar", "16000",
                "-ac", "1", str(path)])
    return str(path)


class BgmTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def stems(self, voice_db, music_db, voice_active=4.0):
        return (make_stem(self.tmp / "voice.wav", voice_db, voice_active),
                make_stem(self.tmp / "music.wav", music_db, 4.0, freq=220))

    @media.requires_ffmpeg
    def test_voice_20_db_over_music_passes(self):
        row = rg.bgm_row(*self.stems(-10, -30), None, 12.0)
        self.assertEqual(row["status"], "PASS")
        self.assertIn("20", row["numbers"])

    @media.requires_ffmpeg
    def test_voice_8_db_over_music_fails(self):
        row = rg.bgm_row(*self.stems(-10, -18), None, 12.0)
        self.assertEqual(row["status"], "FAIL")

    @media.requires_ffmpeg
    def test_headroom_override(self):
        row = rg.bgm_row(*self.stems(-10, -18), None, 6.0)
        self.assertEqual(row["status"], "PASS")

    @media.requires_ffmpeg
    def test_loud_music_where_nobody_speaks_is_not_a_fail(self):
        voice, music = self.stems(-10, -12, voice_active=1.0)
        row = rg.bgm_row(voice, music, [(0.0, 1.0)], 12.0)
        self.assertEqual(row["status"], "FAIL")  # inside the span music is only 2 dB under
        voice, music = self.stems(-10, -30, voice_active=1.0)
        self.assertEqual(rg.bgm_row(voice, music, [(0.0, 1.0)], 12.0)["status"], "PASS")

    @media.requires_ffmpeg
    def test_spans_default_to_where_the_voice_stem_is_active(self):
        voice, music = self.stems(-10, -14, voice_active=1.0)
        # music is only 4 dB under the voice, but the voice stops after 1 s: still a FAIL
        # because that 1 s is measured; silence after it is ignored.
        self.assertEqual(rg.bgm_row(voice, music, None, 12.0)["status"], "FAIL")

    def test_missing_stems_are_not_measured(self):
        row = rg.bgm_row(str(self.tmp / "voice.wav"), str(self.tmp / "music.wav"), None, 12.0)
        self.assertEqual(row["status"], "not measured")
        self.assertIn("voice.wav", row["numbers"])

    @media.requires_ffmpeg
    def test_music_stem_missing_only_is_not_measured_naming_music(self):
        make_stem(self.tmp / "voice.wav", -10)
        row = rg.bgm_row(str(self.tmp / "voice.wav"), str(self.tmp / "music.wav"), None, 12.0)
        self.assertEqual(row["status"], "not measured")
        self.assertIn("music.wav", row["numbers"])
        self.assertNotIn("voice.wav", row["numbers"])

    @media.requires_ffmpeg
    def test_silent_voice_stem_is_not_measured(self):
        voice, music = self.stems(-90, -30)
        self.assertEqual(rg.bgm_row(voice, music, None, 12.0)["status"], "not measured")


def run_main(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rg.main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project, _ = make_project(tmp.name)
        out = self.project / "output"
        out.mkdir()
        make_master(out / "master.mp4", 4.0)
        write(self.project / "av-script.md", av("| 0:00-0:03 | v | a | Hook |",
                                                "| 0:04-0:06 | v | a | Foreshadow |"))
        write(self.project / "vo" / "vo-manifest.json", manifest(dict(words=[word("a", 500, 900)])))

    def rows(self):
        text = (self.project / "work" / "retention-report.md").read_text(encoding="utf-8")
        return {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[2:-1]]
                for l in text.splitlines() if l.startswith("| R")}

    @media.requires_ffmpeg
    def test_report_writes_five_rows_and_exits_0_even_though_a_rule_fails(self):
        code, out, _ = run_main("report", str(self.project))
        self.assertEqual(code, 0)
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows["R1 static frame"][0], "FAIL")
        self.assertEqual(rows["R2 hook"][0], "PASS")
        self.assertEqual(rows["R3 foreshadow"][0], "PASS")
        self.assertEqual(rows["R4 b-roll vs word"][0], "needs verdict")
        self.assertEqual(rows["R5 bgm headroom"][0], "not measured")
        self.assertTrue(all(r[3] == "source: course" for r in rows.values()))
        self.assertIn("R1 static frame", out)

    @media.requires_ffmpeg
    def test_report_rerun_is_idempotent(self):
        run_main("report", str(self.project))
        first = (self.project / "work" / "retention-report.md").read_text()
        run_main("report", str(self.project))
        self.assertEqual(first, (self.project / "work" / "retention-report.md").read_text())

    @media.requires_ffmpeg
    def test_cli_override_flips_a_rule(self):
        code, _, _ = run_main("report", str(self.project), "--static-max-s", "10")
        self.assertEqual(code, 0)
        self.assertEqual(self.rows()["R1 static frame"][0], "PASS")

    @media.requires_ffmpeg
    def test_retention_json_overrides_defaults_and_cli_beats_it(self):
        write(self.project / "work" / "retention.json", json.dumps({"static_max_s": 10}))
        run_main("report", str(self.project))
        self.assertEqual(self.rows()["R1 static frame"][0], "PASS")
        run_main("report", str(self.project), "--static-max-s", "3")
        self.assertEqual(self.rows()["R1 static frame"][0], "FAIL")

    def test_unknown_key_in_retention_json_exits_2(self):
        write(self.project / "work" / "retention.json", json.dumps({"static_max": 1}))
        code, _, err = run_main("report", str(self.project))
        self.assertEqual(code, 2)
        self.assertIn("static_max", err)

    def test_missing_master_exits_2_with_one_line(self):
        (self.project / "output" / "master.mp4").unlink()
        code, _, err = run_main("report", str(self.project))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_missing_project_exits_2(self):
        code, _, err = run_main("report", str(self.project / "nope"))
        self.assertEqual(code, 2)

    def test_missing_argument_exits_2(self):
        self.assertEqual(run_main("report")[0], 2)

    def test_help_exits_0(self):
        self.assertEqual(run_main("--help")[0], 0)

    @media.requires_ffmpeg
    def test_malformed_edit_plan_exits_2(self):
        write(self.project / "work" / "edit-plan.json", "{nope")
        code, _, err = run_main("report", str(self.project))
        self.assertEqual(code, 2)
        self.assertIn("edit-plan", err)

    @media.requires_ffmpeg
    def test_check_exits_1_until_every_cell_is_judged(self):
        run_main("report", str(self.project))
        self.assertEqual(run_main("check", str(self.project))[0], 1)
        qa = self.project / "work" / "retention-qa.md"
        qa.write_text(qa.read_text().replace("| Picture matches the spoken words | |",
                                             "| Picture matches the spoken words | PASS |"))
        self.assertEqual(run_main("check", str(self.project))[0], 0)

    def test_check_without_edit_plan_exits_2(self):
        (self.project / "work" / "edit-plan.json").unlink()
        self.assertEqual(run_main("check", str(self.project))[0], 2)

    @media.requires_ffmpeg
    def test_report_without_av_script_or_manifest_marks_not_measured(self):
        (self.project / "av-script.md").unlink()
        (self.project / "vo" / "vo-manifest.json").unlink()
        self.assertEqual(run_main("report", str(self.project))[0], 0)
        rows = self.rows()
        self.assertEqual(rows["R2 hook"][0], "not measured")
        self.assertEqual(rows["R3 foreshadow"][0], "not measured")


if __name__ == "__main__":
    unittest.main()
