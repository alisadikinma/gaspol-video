import json
import tempfile
import unittest
from pathlib import Path

from tools import renders


class NeedsRenderTest(unittest.TestCase):
    def test_unchanged_done_prompt_does_not_need_render(self):
        prompt = "A gate at dusk, cinematic lighting."
        ledger = {"renders": [{
            "file": "keyframes/scene-03-start.png",
            "phase": "4B",
            "status": "done",
            "prompt_sha256": renders.prompt_sha256(prompt),
        }]}
        self.assertFalse(renders.needs_render(ledger, "keyframes/scene-03-start.png", prompt))

    def test_changed_prompt_needs_render(self):
        old_prompt = "A gate at dusk, cinematic lighting."
        new_prompt = "A gate at dawn, cinematic lighting."
        ledger = {"renders": [{
            "file": "keyframes/scene-03-start.png",
            "phase": "4B",
            "status": "done",
            "prompt_sha256": renders.prompt_sha256(old_prompt),
        }]}
        self.assertTrue(renders.needs_render(ledger, "keyframes/scene-03-start.png", new_prompt))

    def test_failed_entry_always_needs_render(self):
        prompt = "A gate at dusk, cinematic lighting."
        ledger = {"renders": [{
            "file": "keyframes/scene-03-start.png",
            "phase": "4B",
            "status": "failed",
            "prompt_sha256": renders.prompt_sha256(prompt),
        }]}
        self.assertTrue(renders.needs_render(ledger, "keyframes/scene-03-start.png", prompt))

    def test_unknown_file_needs_render(self):
        ledger = {"renders": []}
        self.assertTrue(renders.needs_render(ledger, "keyframes/scene-01-start.png", "anything"))

    def test_crlf_vs_lf_prompt_hash_equal(self):
        lf_prompt = "line one\nline two\n"
        crlf_prompt = "line one\r\nline two\r\n"
        self.assertEqual(renders.prompt_sha256(lf_prompt), renders.prompt_sha256(crlf_prompt))

    def test_trailing_whitespace_per_line_ignored(self):
        a = "line one  \nline two\t\n"
        b = "line one\nline two\n"
        self.assertEqual(renders.prompt_sha256(a), renders.prompt_sha256(b))

    def test_single_trailing_newline_ignored(self):
        self.assertEqual(renders.prompt_sha256("a\nb"), renders.prompt_sha256("a\nb\n"))


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_ledger_loads_empty(self):
        self.assertEqual(renders.load(self.project), {"renders": []})

    def test_invalid_json_raises(self):
        ledger_path = self.project / "renders.json"
        ledger_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(renders.RenderLedgerError) as ctx:
            renders.load(self.project)
        self.assertIn(str(ledger_path), str(ctx.exception))


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_replaces_same_file_entry(self):
        renders.record(self.project, {
            "file": "keyframes/scene-01-start.png", "phase": "4B", "scene": 1,
            "model": "nano-banana-2", "prompt_sha256": "abc", "refs": [],
            "status": "done", "error": None, "cdn_url": "https://x/a.png",
        })
        renders.record(self.project, {
            "file": "keyframes/scene-01-start.png", "phase": "4B", "scene": 1,
            "model": "nano-banana-2", "prompt_sha256": "def", "refs": [],
            "status": "done", "error": None, "cdn_url": "https://x/b.png",
        })
        ledger = renders.load(self.project)
        matching = [e for e in ledger["renders"] if e["file"] == "keyframes/scene-01-start.png"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["prompt_sha256"], "def")

    def test_record_stamps_rendered_at_when_absent(self):
        renders.record(self.project, {
            "file": "keyframes/scene-02-start.png", "phase": "4B", "scene": 2,
            "model": "nano-banana-2", "prompt_sha256": "abc", "refs": [],
            "status": "done", "error": None, "cdn_url": None,
        })
        ledger = renders.load(self.project)
        entry = ledger["renders"][0]
        self.assertTrue(entry["rendered_at"].endswith("Z"))

    def test_record_empty_prompt_hash_still_recorded(self):
        renders.record(self.project, {
            "file": "keyframes/scene-05-start.png", "phase": "4B", "scene": 5,
            "model": "nano-banana-2", "prompt_sha256": renders.prompt_sha256(""), "refs": [],
            "status": "done", "error": None, "cdn_url": None,
        })
        ledger = renders.load(self.project)
        self.assertEqual(len(ledger["renders"]), 1)


class ParseMcpResultTest(unittest.TestCase):
    def test_success_sample(self):
        text = "Saved: /tmp/x/abc.png\nURL: https://cdn.example/abc.png"
        result = renders.parse_mcp_result(text)
        self.assertEqual(result["local_path"], "/tmp/x/abc.png")
        self.assertEqual(result["cdn_url"], "https://cdn.example/abc.png")
        self.assertIsNone(result["error"])

    def test_error_sample(self):
        text = "Error: Audio generation failed"
        result = renders.parse_mcp_result(text)
        self.assertIsNone(result["local_path"])
        self.assertIsNone(result["cdn_url"])
        self.assertEqual(result["error"], text)

    def test_real_indusia_image_gen_result_format(self):
        # Captured verbatim from a real mcp__indusia-image-gen__generate_image call
        # (docs/evals/indusia-render-probe.md) — the real shape is "OK\nlocal: ...
        # \ncdn_url: ...\nuuid: ...", not the plan's illustrative "Saved:/URL:" example.
        text = (
            "OK\n"
            "local: /tmp/gv2-probe/image/20260913-110312-e9469ea8-af27-11f1-98c6-762a55ae2c2d.png\n"
            "cdn_url: https://7a4964de26acd06ff740870066a92ff8.r2.cloudflarestorage.com/"
            "geminigen-prd-upload-bucket/1795594/generated_result/image/"
            "e9469ea8-af27-11f1-98c6-762a55ae2c2d/gen/20260913_040305_0_UTC_0.png"
            "?response-content-type=application%2Foctet-stream&X-Amz-Algorithm=AWS4-HMAC-SHA256\n"
            "uuid: e9469ea8-af27-11f1-98c6-762a55ae2c2d"
        )
        result = renders.parse_mcp_result(text)
        self.assertEqual(
            result["local_path"],
            "/tmp/gv2-probe/image/20260913-110312-e9469ea8-af27-11f1-98c6-762a55ae2c2d.png",
        )
        self.assertTrue(result["cdn_url"].startswith("https://7a4964de26acd06ff740870066a92ff8"))
        self.assertIsNone(result["error"])

    def test_local_line_path_with_spaces_and_webp_extension(self):
        # the old regex (`\.(?:png|jpg|jpeg|mp4)`) could not have matched either the
        # space in the path or the .webp extension — the explicit "local:" line must
        # be read whole, not re-derived from a pattern.
        text = "OK\nlocal: /tmp/gv2 probe/clip take 2.webp\ncdn_url: https://cdn.example/x.webp"
        result = renders.parse_mcp_result(text)
        self.assertEqual(result["local_path"], "/tmp/gv2 probe/clip take 2.webp")
        self.assertEqual(result["cdn_url"], "https://cdn.example/x.webp")
        self.assertIsNone(result["error"])

    def test_local_line_mov_extension(self):
        text = "OK\nlocal: /tmp/gv2-probe/video/clip.mov\ncdn_url: https://cdn.example/clip.mov"
        result = renders.parse_mcp_result(text)
        self.assertEqual(result["local_path"], "/tmp/gv2-probe/video/clip.mov")


class VideoRenderEligibilityTest(unittest.TestCase):
    def _scene(self, **overrides):
        base = {
            "platform": "veo",
            "mode": "frame",
            "duration_s": 8,
            "aspect": "16:9",
            "refs": ["ref/scene-01-start.png"],
        }
        base.update(overrides)
        return base

    def test_non_veo_platform_is_prompt_only(self):
        eligible, reason = renders.video_render_eligibility(
            self._scene(platform="kling", mode="i2v", duration_s=5, refs=[])
        )
        self.assertFalse(eligible)
        self.assertIn("prompt-only", reason)

    def test_seedance_platform_is_prompt_only(self):
        eligible, reason = renders.video_render_eligibility(self._scene(platform="seedance"))
        self.assertFalse(eligible)
        self.assertIn("prompt-only", reason)

    def test_extend_mode_ineligible(self):
        eligible, reason = renders.video_render_eligibility(self._scene(mode="extend"))
        self.assertFalse(eligible)
        self.assertIn("Scene Extension", reason)

    def test_duration_5_ineligible(self):
        eligible, reason = renders.video_render_eligibility(self._scene(duration_s=5))
        self.assertFalse(eligible)
        self.assertIn("duration", reason)

    def test_aspect_1_1_ineligible(self):
        eligible, reason = renders.video_render_eligibility(self._scene(aspect="1:1"))
        self.assertFalse(eligible)
        self.assertIn("aspect", reason)

    def test_frame_mode_with_3_refs_ineligible(self):
        eligible, reason = renders.video_render_eligibility(
            self._scene(mode="frame", refs=["a.png", "b.png", "c.png"])
        )
        self.assertFalse(eligible)
        self.assertIn("too many refs", reason)

    def test_ingredients_mode_with_3_refs_eligible(self):
        eligible, reason = renders.video_render_eligibility(
            self._scene(mode="ingredients", refs=["a.png", "b.png", "c.png"])
        )
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_veo_frame_8s_16_9_one_ref_eligible(self):
        eligible, reason = renders.video_render_eligibility(self._scene())
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_duration_as_float_eligible(self):
        eligible, reason = renders.video_render_eligibility(self._scene(duration_s=8.0))
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_duration_as_numeric_string_eligible(self):
        # a scene built from JSON on the CLI (--json '{"duration_s": "8", ...}') hands
        # duration_s through as a string — it must coerce, not silently mismatch 8.
        eligible, reason = renders.video_render_eligibility(self._scene(duration_s="8"))
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_duration_non_numeric_string_is_ineligible_not_a_crash(self):
        eligible, reason = renders.video_render_eligibility(self._scene(duration_s="soon"))
        self.assertFalse(eligible)
        self.assertIn("not a number", reason)


class MainCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.prompt_file = self.project / "prompt.txt"
        self.prompt_file.write_text("A gate at dusk, cinematic lighting.")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, argv, capsys=None):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = renders.main(argv)
        return rc, buf.getvalue()

    def test_hash_subcommand_prints_prompt_sha256(self):
        rc, out = self._run([str(self.project), "hash", "--prompt-file", str(self.prompt_file)])
        self.assertEqual(rc, 0)
        expected = renders.prompt_sha256(self.prompt_file.read_text())
        self.assertEqual(out.strip(), expected)

    def test_check_subcommand_prints_render_when_unknown(self):
        rc, out = self._run([str(self.project), "check", "--file", "keyframes/x.png",
                              "--prompt-file", str(self.prompt_file)])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "render")

    def test_check_subcommand_prints_up_to_date_when_done_and_unchanged(self):
        prompt = self.prompt_file.read_text()
        (self.project / "keyframes").mkdir(parents=True, exist_ok=True)
        (self.project / "keyframes/x.png").write_bytes(b"png")
        renders.record(self.project, {
            "file": "keyframes/x.png", "phase": "4B", "status": "done",
            "prompt_sha256": renders.prompt_sha256(prompt),
        })
        rc, out = self._run([str(self.project), "check", "--file", "keyframes/x.png",
                              "--prompt-file", str(self.prompt_file)])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "up-to-date")

    def test_record_subcommand_writes_ledger_and_strips_cdn_query_string(self):
        entry = {
            "file": "keyframes/x.png", "phase": "4B", "status": "done",
            "cdn_url": "https://cdn.example/x.png?X-Amz-Signature=abc&extra=1",
        }
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 0)
        ledger = renders.load(self.project)
        self.assertEqual(len(ledger["renders"]), 1)
        self.assertEqual(ledger["renders"][0]["cdn_url"], "https://cdn.example/x.png")

    def test_record_subcommand_computes_prompt_sha256_from_prompt_file(self):
        entry = {"file": "keyframes/y.png", "phase": "4A", "status": "done"}
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry),
                              "--prompt-file", str(self.prompt_file)])
        self.assertEqual(rc, 0)
        ledger = renders.load(self.project)
        self.assertEqual(ledger["renders"][0]["prompt_sha256"],
                          renders.prompt_sha256(self.prompt_file.read_text()))

    def test_record_subcommand_rejects_missing_required_field(self):
        entry = {"file": "keyframes/z.png", "status": "done"}  # no phase
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 1)

    def test_record_subcommand_rejects_invalid_phase(self):
        entry = {"file": "keyframes/z.png", "phase": "7", "status": "done"}
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 1)

    def test_record_subcommand_accepts_phase_6_music_entry(self):
        entry = {"file": "output/music.mp3", "phase": "6", "status": "done"}
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 0)
        self.assertEqual(renders.load(self.project)["renders"][0]["file"], "output/music.mp3")

    def test_record_subcommand_rejects_invalid_status(self):
        entry = {"file": "keyframes/z.png", "phase": "4A", "status": "maybe"}
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 1)

    def test_record_subcommand_accepts_json_file(self):
        entry_path = self.project / "entry.json"
        entry_path.write_text(json.dumps({
            "file": "keyframes/w.png", "phase": "5", "status": "failed",
        }))
        rc, out = self._run([str(self.project), "record", "--json-file", str(entry_path)])
        self.assertEqual(rc, 0)
        ledger = renders.load(self.project)
        self.assertEqual(ledger["renders"][0]["status"], "failed")

    def test_eligible_subcommand_prints_eligible(self):
        scene = {"platform": "veo", "mode": "frame", "duration_s": 8, "aspect": "16:9",
                  "refs": ["a.png"]}
        rc, out = self._run([str(self.project), "eligible", "--json", json.dumps(scene)])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "eligible")

    def test_eligible_subcommand_prints_ineligible_with_reason(self):
        scene = {"platform": "kling", "mode": "i2v", "duration_s": 5, "aspect": "16:9", "refs": []}
        rc, out = self._run([str(self.project), "eligible", "--json", json.dumps(scene)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.strip().startswith("ineligible:"))
        self.assertIn("prompt-only", out)


class ArchiveFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()

    def _make(self, rel, data=b"paid-bytes"):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_moves_keyframe_into_arsip_with_reason(self):
        self._make("keyframes/scene-03.png")
        dest = renders.archive_file(self.project, "keyframes/scene-03.png",
                                    reason="prompt berubah", phase="4B")
        self.assertEqual(dest, self.project / "_arsip" / "keyframe-scene-03-v1-prompt-berubah.png")
        self.assertTrue(dest.exists())
        self.assertFalse((self.project / "keyframes/scene-03.png").exists())

    def test_move_keeps_bytes(self):
        import hashlib
        src = self._make("keyframes/scene-03.png", b"\x89PNG\x00real bytes" * 50)
        before = hashlib.sha256(src.read_bytes()).hexdigest()
        dest = renders.archive_file(self.project, "keyframes/scene-03.png", "x", "4B")
        self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(), before)

    def test_missing_file_returns_none(self):
        self.assertIsNone(renders.archive_file(self.project, "keyframes/nope.png", "x", "4B"))

    def test_second_and_third_archive_count_up(self):
        names = []
        for _ in range(3):
            self._make("keyframes/scene-03.png")
            names.append(renders.archive_file(self.project, "keyframes/scene-03.png", "r", "4B").name)
        self.assertEqual(names, ["keyframe-scene-03-v1-r.png", "keyframe-scene-03-v2-r.png",
                                 "keyframe-scene-03-v3-r.png"])

    def test_removed_v1_is_not_reused(self):
        self._make("keyframes/scene-03.png")
        first = renders.archive_file(self.project, "keyframes/scene-03.png", "r", "4B")
        self._make("keyframes/scene-03.png")
        renders.archive_file(self.project, "keyframes/scene-03.png", "r", "4B")
        first.unlink()
        self._make("keyframes/scene-03.png")
        third = renders.archive_file(self.project, "keyframes/scene-03.png", "r", "4B")
        self.assertEqual(third.name, "keyframe-scene-03-v3-r.png")

    def test_numeric_not_string_max(self):
        self._make("_arsip/keyframe-scene-03-v10-x.png")
        self._make("_arsip/keyframe-scene-03-v9-x.png")
        self._make("keyframes/scene-03.png")
        dest = renders.archive_file(self.project, "keyframes/scene-03.png", "r", "4B")
        self.assertEqual(dest.name, "keyframe-scene-03-v11-r.png")

    def test_prefix_stem_does_not_share_numbering(self):
        self._make("_arsip/keyframe-scene-03-v5-x.png")
        self._make("keyframes/scene-0.png")
        dest = renders.archive_file(self.project, "keyframes/scene-0.png", "r", "4B")
        self.assertEqual(dest.name, "keyframe-scene-0-v1-r.png")

    def test_empty_reason_is_diganti(self):
        self._make("keyframes/a.png")
        dest = renders.archive_file(self.project, "keyframes/a.png", "", "4B")
        self.assertEqual(dest.name, "keyframe-a-v1-diganti.png")

    def test_reason_slug_punctuation(self):
        self._make("keyframes/a.png")
        dest = renders.archive_file(self.project, "keyframes/a.png", "Prompt Berubah!! / wajah", "4B")
        self.assertEqual(dest.name, "keyframe-a-v1-prompt-berubah-wajah.png")

    def test_long_reason_cut_to_40(self):
        self._make("keyframes/a.png")
        dest = renders.archive_file(self.project, "keyframes/a.png", "x" * 100, "4B")
        self.assertEqual(dest.name, "keyframe-a-v1-" + "x" * 40 + ".png")

    def test_non_ascii_reason_dropped(self):
        self._make("keyframes/a.png")
        dest = renders.archive_file(self.project, "keyframes/a.png", "wajah é muka", "4B")
        self.assertEqual(dest.name, "keyframe-a-v1-wajah-muka.png")
        self._make("keyframes/b.png")
        dest = renders.archive_file(self.project, "keyframes/b.png", "日本語", "4B")
        self.assertEqual(dest.name, "keyframe-b-v1-diganti.png")

    def test_creates_arsip_when_absent(self):
        self._make("keyframes/a.png")
        self.assertFalse((self.project / "_arsip").exists())
        renders.archive_file(self.project, "keyframes/a.png", "r", "4B")
        self.assertTrue((self.project / "_arsip").is_dir())

    def test_phase_maps_to_kind(self):
        for phase, kind in (("4A", "gambar"), ("4B", "keyframe"), ("5", "klip"), ("6", "audio")):
            self._make("work/f.bin")
            dest = renders.archive_file(self.project, "work/f.bin", "r", phase)
            self.assertTrue(dest.name.startswith(f"{kind}-f-v"), dest.name)

    def test_phase_from_ledger_when_not_given(self):
        renders.record(self.project, {"file": "clips/s.mp4", "phase": "4B", "status": "done"})
        self._make("clips/s.mp4")
        dest = renders.archive_file(self.project, "clips/s.mp4", "r")
        self.assertTrue(dest.name.startswith("keyframe-s-v1-"), dest.name)

    def test_explicit_phase_overrides_ledger(self):
        renders.record(self.project, {"file": "clips/s.mp4", "phase": "4B", "status": "done"})
        self._make("clips/s.mp4")
        dest = renders.archive_file(self.project, "clips/s.mp4", "r", "5")
        self.assertTrue(dest.name.startswith("klip-s-v1-"), dest.name)

    def test_extension_fallback(self):
        for rel, kind in (("clips/a.mp4", "klip"), ("clips/b.mov", "klip"), ("vo/c.wav", "audio"),
                          ("vo/d.mp3", "audio"), ("ref/e.png", "gambar")):
            self._make(rel)
            dest = renders.archive_file(self.project, rel, "r")
            self.assertTrue(dest.name.startswith(kind + "-"), dest.name)

    def test_invalid_ledger_json_falls_back_to_extension(self):
        (self.project / "renders.json").write_text("{not json")
        self._make("clips/a.mp4")
        dest = renders.archive_file(self.project, "clips/a.mp4", "r")
        self.assertTrue(dest.name.startswith("klip-a-v1-"), dest.name)

    def test_relative_escape_raises(self):
        outside = Path(self._tmp.name) / "x.png"
        outside.write_bytes(b"x")
        with self.assertRaises(ValueError) as ctx:
            renders.archive_file(self.project, "../x.png", "r", "4B")
        self.assertIn("file escapes project", str(ctx.exception))
        self.assertTrue(outside.exists())

    def test_absolute_escape_raises(self):
        outside = Path(self._tmp.name) / "y.png"
        outside.write_bytes(b"y")
        with self.assertRaises(ValueError):
            renders.archive_file(self.project, str(outside), "r", "4B")
        self.assertTrue(outside.exists())

    def test_directory_raises(self):
        (self.project / "keyframes" / "sub").mkdir(parents=True)
        with self.assertRaises(ValueError):
            renders.archive_file(self.project, "keyframes/sub", "r", "4B")

    def test_symlink_raises(self):
        target = self._make("keyframes/real.png")
        link = self.project / "keyframes" / "link.png"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            renders.archive_file(self.project, "keyframes/link.png", "r", "4B")
        self.assertTrue(target.exists())

    def test_ledger_entry_untouched(self):
        renders.record(self.project, {"file": "keyframes/a.png", "phase": "4B", "status": "done"})
        before = (self.project / "renders.json").read_text()
        self._make("keyframes/a.png")
        renders.archive_file(self.project, "keyframes/a.png", "r")
        self.assertEqual((self.project / "renders.json").read_text(), before)


class ArchiveCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        (self.project / "keyframes").mkdir(parents=True)

    def _run(self, argv):
        import io
        import contextlib
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = renders.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_archive_prints_move(self):
        (self.project / "keyframes/scene-03.png").write_bytes(b"x")
        rc, out, _ = self._run([str(self.project), "archive", "--file", "keyframes/scene-03.png",
                                "--reason", "prompt berubah"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(),
                         "archived keyframes/scene-03.png -> _arsip/gambar-scene-03-v1-prompt-berubah.png")

    def test_archive_nothing_to_archive(self):
        rc, out, _ = self._run([str(self.project), "archive", "--file", "keyframes/none.png"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "nothing to archive: keyframes/none.png")

    def test_archive_value_error_exit_1(self):
        rc, out, err = self._run([str(self.project), "archive", "--file", "../x.png"])
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("renders: "), err)
        self.assertIn("file escapes project", err)


class ArchiveSafetyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()

    def _make(self, rel, data=b"paid"):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_arsip_symlink_refused_and_target_untouched(self):
        import os
        self._make("keyframes/a.png")
        other = Path(self._tmp.name) / "elsewhere"
        other.mkdir()
        os.symlink(other, self.project / "_arsip")
        with self.assertRaises(ValueError):
            renders.archive_file(self.project, "keyframes/a.png", "x", "4B")
        self.assertEqual(list(other.iterdir()), [])
        self.assertTrue((self.project / "keyframes/a.png").exists())

    def test_non_dict_ledger_entry_falls_back_to_extension(self):
        self._make("clips/a.mp4")
        (self.project / "renders.json").write_text(json.dumps({"renders": ["junk", 5, None]}))
        dest = renders.archive_file(self.project, "clips/a.mp4", "x")
        self.assertEqual(dest.name, "klip-a-v1-x.mp4")

    def test_ledger_oserror_falls_back_to_extension(self):
        from unittest import mock
        self._make("clips/a.mp4")
        with mock.patch.object(renders, "load", side_effect=PermissionError("denied")):
            dest = renders.archive_file(self.project, "clips/a.mp4", "x")
        self.assertEqual(dest.name, "klip-a-v1-x.mp4")

    def test_refuses_file_not_in_a_subfolder(self):
        self._make("renders.json", b"{}")
        with self.assertRaises(ValueError):
            renders.archive_file(self.project, "renders.json", "x")
        self.assertTrue((self.project / "renders.json").exists())

    def test_refuses_file_inside_arsip_or_tmp(self):
        self._make("_arsip/x.png")
        self._make(".tmp/x.png")
        for rel in ("_arsip/x.png", ".tmp/x.png", "_ARSIP/x.png", "keyframes/../.tmp/x.png"):
            with self.assertRaises(ValueError, msg=rel):
                renders.archive_file(self.project, rel, "x")
        self.assertTrue((self.project / "_arsip/x.png").exists())
        self.assertTrue((self.project / ".tmp/x.png").exists())


class CheckMissingFileTest(unittest.TestCase):
    def test_check_says_render_when_file_is_gone_despite_matching_hash(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            (proj / "keyframes").mkdir()
            pf = proj / "prompt.txt"
            pf.write_text("A gate at dusk.")
            renders.record(proj, {"file": "keyframes/s.png", "phase": "4B", "status": "done",
                                  "prompt_sha256": renders.prompt_sha256("A gate at dusk.")})
            argv = [str(proj), "check", "--file", "keyframes/s.png", "--prompt-file", str(pf)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                renders.main(argv)
            self.assertEqual(out.getvalue().strip(), "render")
            (proj / "keyframes/s.png").write_bytes(b"x")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                renders.main(argv)
            self.assertEqual(out.getvalue().strip(), "up-to-date")


if __name__ == "__main__":
    unittest.main()
