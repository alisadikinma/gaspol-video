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


if __name__ == "__main__":
    unittest.main()
