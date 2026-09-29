import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import asset_home


class HomeEnvTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        patcher = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)


class LibraryTest(HomeEnvTestCase):
    def test_library_honours_home_and_creates_the_directory(self):
        lib = asset_home.library("sfx")
        self.assertEqual(lib, self.home / "library" / "sfx")
        self.assertTrue(lib.is_dir())

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            asset_home.library("videos")

    def test_recipes_live_in_the_plugin_not_home(self):
        path = asset_home.recipes("music")
        self.assertEqual(path.name, "palette.json")
        self.assertNotIn(str(self.home), str(path))
        self.assertTrue(path.exists())


def make_source(root, name, kind, entries):
    """A fake plugin-cache library. entries: [(id, bytes, mtime)]."""
    key, sub = ("clips", "clips") if kind == "sfx" else ("tracks", "tracks")
    lib = root / "cache" / name / "media" / kind / "library"
    (lib / sub).mkdir(parents=True)
    catalog = {key: []}
    for id_, data, mtime in entries:
        f = lib / sub / f"{id_}.mp3"
        f.write_bytes(data)
        os.utime(f, (mtime, mtime))
        catalog[key].append({"id": id_, "file": f"{sub}/{id_}.mp3", "from": name})
    (lib / "catalog.json").write_text(json.dumps(catalog))
    return lib


class AdoptTest(HomeEnvTestCase):
    def _catalog(self, kind="sfx"):
        key = "clips" if kind == "sfx" else "tracks"
        return json.loads((asset_home.library(kind) / "catalog.json").read_text())[key]

    def test_adopt_merges_versions_and_newest_mtime_wins(self):
        old = make_source(self.root, "3.4.0", "sfx", [("pop", b"old-pop", 1000), ("hum", b"hum", 1000)])
        new = make_source(self.root, "3.5.0", "sfx", [("pop", b"new-pop", 2000)])
        logs = []
        n = asset_home.adopt("sfx", sources=[old, new], log=logs.append)
        self.assertEqual(n, 2)
        lib = asset_home.library("sfx")
        self.assertEqual((lib / "clips" / "pop.mp3").read_bytes(), b"new-pop")
        self.assertEqual((lib / "clips" / "hum.mp3").read_bytes(), b"hum")
        entries = {c["id"]: c for c in self._catalog()}
        self.assertEqual(sorted(entries), ["hum", "pop"])
        self.assertEqual(entries["pop"]["from"], "3.5.0")
        self.assertTrue(any(l.startswith("adopted 1 sfx file(s) from") and str(new) in l for l in logs))
        self.assertTrue(any(l.startswith("adopted 1 sfx file(s) from") and str(old) in l for l in logs))

    def test_adopt_copies_and_never_moves(self):
        src = make_source(self.root, "3.5.0", "music", [("warm", b"warm-bytes", 1000)])
        asset_home.adopt("music", sources=[src], log=lambda *_: None)
        self.assertEqual((src / "tracks" / "warm.mp3").read_bytes(), b"warm-bytes")
        self.assertEqual((asset_home.library("music") / "tracks" / "warm.mp3").read_bytes(), b"warm-bytes")
        self.assertEqual([t["id"] for t in self._catalog("music")], ["warm"])

    def test_second_call_adopts_nothing(self):
        src = make_source(self.root, "3.5.0", "sfx", [("pop", b"pop", 1000)])
        self.assertEqual(asset_home.adopt("sfx", sources=[src], log=lambda *_: None), 1)
        logs = []
        self.assertEqual(asset_home.adopt("sfx", sources=[src], log=logs.append), 0)
        self.assertEqual(logs, [])

    def test_empty_sources_adopt_zero_and_write_no_catalog(self):
        self.assertEqual(asset_home.adopt("sfx", sources=[], log=lambda *_: None), 0)
        self.assertFalse((asset_home.library("sfx") / "catalog.json").exists())

    def test_source_with_a_missing_file_skips_that_entry(self):
        src = make_source(self.root, "3.5.0", "sfx", [("pop", b"pop", 1000), ("gone", b"x", 1000)])
        (src / "clips" / "gone.mp3").unlink()
        self.assertEqual(asset_home.adopt("sfx", sources=[src], log=lambda *_: None), 1)
        self.assertEqual([c["id"] for c in self._catalog()], ["pop"])

    def test_existing_home_catalog_is_left_alone(self):
        lib = asset_home.library("sfx")
        (lib / "catalog.json").write_text(json.dumps({"clips": [{"id": "mine", "file": "clips/mine.mp3"}]}))
        src = make_source(self.root, "3.5.0", "sfx", [("pop", b"pop", 1000)])
        self.assertEqual(asset_home.adopt("sfx", sources=[src], log=lambda *_: None), 0)
        self.assertEqual([c["id"] for c in self._catalog()], ["mine"])

    def test_images_have_nothing_to_adopt(self):
        self.assertEqual(asset_home.adopt("images", sources=[], log=lambda *_: None), 0)


if __name__ == "__main__":
    unittest.main()
