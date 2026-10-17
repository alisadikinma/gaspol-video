import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import guide_vo


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class GuideVoTest(unittest.TestCase):
    LINES = [{"id": "scene-03", "text": "[curious] Apa yang menahannya?"}]

    def _gen(self, d, **kw):
        calls = []

        def urlopen(req, timeout=0):
            calls.append(json.loads(req.data))
            return FakeResp(b"mp3-bytes")

        paths = guide_vo.generate(self.LINES, "voice-x", "key", d, urlopen=urlopen, log=lambda *_: None, **kw)
        return paths, calls

    def test_one_file_per_take_named_by_line(self):
        with tempfile.TemporaryDirectory() as d:
            paths, calls = self._gen(d, stabilities=(0.0, 0.5))
            self.assertEqual([Path(p).name for p in paths],
                             ["scene-03-pemandu-take1.mp3", "scene-03-pemandu-take2.mp3"])
            self.assertEqual([c["voice_settings"]["stability"] for c in calls], [0.0, 0.5])
            self.assertEqual(calls[0]["model_id"], "eleven_v3")

    def test_existing_take_is_not_requested_again(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "scene-03-pemandu-take1.mp3").write_bytes(b"old")
            _, calls = self._gen(d, stabilities=(0.0, 0.5))
            self.assertEqual(len(calls), 1)

    def test_force_regenerates(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "scene-03-pemandu-take1.mp3").write_bytes(b"old")
            _, calls = self._gen(d, stabilities=(0.0,), force=True)
            self.assertEqual(len(calls), 1)

    def test_speed_and_language_in_body(self):
        with tempfile.TemporaryDirectory() as d:
            _, calls = self._gen(d, stabilities=(0.5,), speed=1.15, language="id")
            self.assertEqual(calls[0]["voice_settings"]["speed"], 1.15)
            self.assertEqual(calls[0]["language_code"], "id")

    def test_em_dash_rejected_before_any_request(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                guide_vo.generate([{"id": "a", "text": "satu — dua"}], "v", "k", d,
                                  urlopen=lambda *a, **k: self.fail("billed"), log=lambda *_: None)

    def test_line_without_id_or_text_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                guide_vo.generate([{"text": "x"}], "v", "k", d, urlopen=None, log=lambda *_: None)

    def test_cli_needs_a_voice(self):
        with tempfile.TemporaryDirectory() as d:
            plan = Path(d) / "p.json"
            plan.write_text(json.dumps(self.LINES))
            err = io.StringIO()
            import contextlib
            with contextlib.redirect_stderr(err):
                rc = guide_vo.main([str(plan), d], env={"ELEVENLABS_API_KEY": "k"})
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
