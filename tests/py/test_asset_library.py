import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools import asset_library

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PROMPT = "16:9. A tidy warehouse aisle with a forklift.\nSoft daylight."


class LibraryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        patcher = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def image(self, name="in.png", data=PNG):
        path = self.root / name
        path.write_bytes(data)
        return path

    def add(self, prompt=PROMPT, aspect="16:9", **kw):
        return asset_library.add(self.image(), prompt, aspect, model="nano-banana-2", **kw)


class RoundTripTest(LibraryTestCase):
    def test_add_then_find_round_trip(self):
        id_ = self.add(tags=["gudang", "forklift"], description="warehouse aisle")
        found = asset_library.find(PROMPT, "16:9")
        self.assertEqual(found, self.home / "library" / "images" / f"{id_}.png")
        self.assertEqual(found.read_bytes(), PNG)
        self.assertTrue(id_.endswith("-16x9"))
        self.assertEqual(len(id_.split("-")[0]), 16)
        entry = json.loads((self.home / "library" / "images" / "catalog.json").read_text())["images"][0]
        self.assertEqual(entry["id"], id_)
        self.assertEqual(entry["tags"], ["gudang", "forklift"])
        self.assertEqual(entry["model"], "nano-banana-2")


class GuardTest(LibraryTestCase):
    def test_every_project_specific_word_is_refused(self):
        words = [("cast-c1-face.png", "cast-"), ("brand-logo.png", "brand-"),
                 ("ui-dashboard.png", "ui-"), ("product-tank.png", "product-"),
                 ("costume-kai.png", "costume-"), ("env-gate.png", "env-"),
                 ("Maintain exact facial identity", "Maintain exact facial identity"),
                 ("continuation from scene-04-end.png", "scene-04-")]
        for word, token in words:
            with self.subTest(word=word):
                with self.assertRaises(asset_library.LibraryError) as ctx:
                    self.add(prompt=f"A room. {word}. Daylight.")
                self.assertIn(token, str(ctx.exception))
        self.assertIsNone(asset_library.find("A room. cast-c1-face.png. Daylight.", "16:9"))

    def test_non_image_file_is_refused(self):
        with self.assertRaises(asset_library.LibraryError):
            asset_library.add(self.image("x.png", b"not an image at all"), PROMPT, "16:9")

    def test_jpeg_is_accepted_and_stored_as_png_name(self):
        id_ = asset_library.add(self.image("x.jpg", JPEG), PROMPT, "16:9")
        self.assertEqual(asset_library.find(PROMPT, "16:9").name, f"{id_}.png")

    def test_bad_aspect_is_refused(self):
        with self.assertRaises(asset_library.LibraryError):
            self.add(aspect="21:9")

    def test_duplicate_add_needs_force(self):
        self.add(description="first")
        with self.assertRaises(asset_library.LibraryError):
            self.add(description="second")
        self.add(description="second", force=True)
        entries = asset_library.list_entries()
        self.assertEqual([e["description"] for e in entries], ["second"])


class FindTest(LibraryTestCase):
    def test_other_aspect_misses(self):
        self.add()
        self.assertIsNone(asset_library.find(PROMPT, "9:16"))

    def test_whitespace_only_change_hits(self):
        self.add()
        noisy = PROMPT.replace("\n", "  \r\n") + "\n"
        self.assertIsNotNone(asset_library.find(noisy, "16:9"))

    def test_changed_word_misses(self):
        self.add()
        self.assertIsNone(asset_library.find(PROMPT.replace("tidy", "messy"), "16:9"))


class UseTest(LibraryTestCase):
    def test_use_copies_and_refuses_overwrite_without_force(self):
        id_ = self.add()
        dest = self.root / "proj" / "ref" / "env-x.png"
        asset_library.use(id_, dest)
        self.assertEqual(dest.read_bytes(), PNG)
        dest.write_bytes(b"changed")
        with self.assertRaises(asset_library.LibraryError):
            asset_library.use(id_, dest)
        self.assertEqual(dest.read_bytes(), b"changed")
        asset_library.use(id_, dest, force=True)
        self.assertEqual(dest.read_bytes(), PNG)

    def test_use_unknown_id_is_refused(self):
        with self.assertRaises(asset_library.LibraryError):
            asset_library.use("nope-16x9", self.root / "o.png")


class ListTest(LibraryTestCase):
    def test_tag_filters(self):
        self.add(tags=["gudang"])
        self.add(prompt="A quiet beach at dawn.", tags=["pantai"])
        self.assertEqual(len(asset_library.list_entries()), 2)
        hits = asset_library.list_entries("pantai")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["tags"], ["pantai"])


class CliTest(LibraryTestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = asset_library.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_cli_add_find_list_use(self):
        pf = self.root / "p.txt"
        pf.write_text(PROMPT)
        code, _, _ = self.run_cli("add", "--file", str(self.image()), "--prompt-file", str(pf),
                                  "--aspect", "16:9", "--model", "nano-banana-2",
                                  "--tags", "gudang,forklift", "--description", "aisle",
                                  "--project", str(self.root / "proj"))
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("find", "--prompt-file", str(pf), "--aspect", "16:9")
        self.assertEqual(code, 0)
        path = out.strip()
        self.assertTrue(Path(path).is_file())
        code, out, _ = self.run_cli("find", "--prompt-file", str(pf), "--aspect", "1:1")
        self.assertEqual(code, 1)
        code, out, _ = self.run_cli("list", "--tag", "forklift")
        self.assertIn("aisle", out)
        dest = self.root / "proj" / "ref" / "a.png"
        code, _, _ = self.run_cli("use", "--id", Path(path).stem, "--to", str(dest))
        self.assertEqual(code, 0)
        self.assertTrue(dest.is_file())

    def test_cli_guard_exits_2(self):
        pf = self.root / "p.txt"
        pf.write_text("A face. cast-c1-face.png")
        code, _, err = self.run_cli("add", "--file", str(self.image()), "--prompt-file", str(pf),
                                    "--aspect", "16:9")
        self.assertEqual(code, 2)
        self.assertIn("cast-", err)


if __name__ == "__main__":
    unittest.main()


class LetteredContinuityGuardTest(unittest.TestCase):
    def test_lettered_scene_continuity_ref_is_project_specific(self):
        # Real projects name scenes 01b / 03a (catalog-4), so scene-01b-end.png is a continuity
        # frame exactly like scene-01-end.png and must never enter the shared library.
        self.assertTrue(asset_library._PROJECT_SPECIFIC.search(
            "continuation from scene-01b-end.png, same porch"))
