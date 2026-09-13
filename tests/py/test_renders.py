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
        entry = {"file": "keyframes/z.png", "phase": "6", "status": "done"}
        rc, out = self._run([str(self.project), "record", "--json", json.dumps(entry)])
        self.assertEqual(rc, 1)

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


if __name__ == "__main__":
    unittest.main()
