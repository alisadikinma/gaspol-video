import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import asset_home, gen_sfx


class GenSfxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self.tmp.name)
        (self.lib / "clips").mkdir()
        (self.lib / "palette.json").write_text(json.dumps({"recipes": [
            {"id": "pop-reveal", "prompt": "soft UI pop, clean, no reverb",
             "duration_s": 0.4, "category": "emphasis", "tags": ["ui", "reveal"]},
            {"id": "amb-factory-floor", "prompt": "distant conveyor hum, industrial hall",
             "duration_s": 12.0, "category": "ambience", "tags": ["industrial"]},
        ]}))
        (self.lib / "catalog.json").write_text(json.dumps({"clips": []}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_ids_are_the_ones_not_yet_in_the_catalog(self):
        (self.lib / "catalog.json").write_text(json.dumps({"clips": [{"id": "pop-reveal"}]}))
        missing = gen_sfx.missing_recipes(self.lib)
        self.assertEqual([r["id"] for r in missing], ["amb-factory-floor"])

    def test_force_regenerates_everything(self):
        (self.lib / "catalog.json").write_text(json.dumps({"clips": [{"id": "pop-reveal"}]}))
        missing = gen_sfx.missing_recipes(self.lib, force=True)
        self.assertEqual(len(missing), 2)

    def test_only_filters_by_id(self):
        missing = gen_sfx.missing_recipes(self.lib, only=["amb-factory-floor"])
        self.assertEqual([r["id"] for r in missing], ["amb-factory-floor"])

    def test_unknown_only_id_is_reported_not_silently_empty(self):
        with self.assertRaises(gen_sfx.LibraryError) as ctx:
            gen_sfx.missing_recipes(self.lib, only=["not-a-recipe"])
        self.assertIn("not-a-recipe", str(ctx.exception))

    def test_catalog_entry_records_provenance(self):
        entry = gen_sfx.catalog_entry(
            recipe={"id": "pop-reveal", "prompt": "soft UI pop", "duration_s": 0.4,
                    "category": "emphasis", "tags": ["ui"]},
            file="clips/pop-reveal.mp3", loudness_lufs=-20.1, peak_dbfs=-1.5,
        )
        for field in ("id", "file", "category", "tags", "duration_s", "peak_dbfs",
                      "loudness_lufs", "source", "model", "license", "prompt", "used_in"):
            self.assertIn(field, entry, f"catalog entry is missing {field}")
        self.assertEqual(entry["source"], "elevenlabs-sfx")
        self.assertEqual(entry["used_in"], [])

    def test_normalisation_targets_are_the_calibrated_ones(self):
        args = gen_sfx.loudnorm_args()
        self.assertIn(f"I={gen_sfx.TARGET_LUFS}", args)
        self.assertIn(f"TP={gen_sfx.TARGET_PEAK_DBFS}", args)

    def test_dry_run_writes_nothing(self):
        result = gen_sfx.generate(self.lib, env={"ELEVENLABS_API_KEY": "k"}, dry_run=True,
                                 log=lambda *_: None)
        self.assertEqual(result["written"], [])
        self.assertEqual(json.loads((self.lib / "catalog.json").read_text())["clips"], [])

    def test_missing_key_degrades_and_names_the_recipes_it_could_not_make(self):
        result = gen_sfx.generate(self.lib, env={}, log=lambda *_: None)
        self.assertTrue(result["degraded"])
        self.assertIn("ELEVENLABS_API_KEY", result["reason"])
        self.assertEqual(sorted(result["pending"]), ["amb-factory-floor", "pop-reveal"])


class MissingPaletteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self.tmp.name)  # no palette.json written
        (self.lib / "clips").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_palette_raises_when_missing(self):
        with self.assertRaises(gen_sfx.LibraryError) as ctx:
            gen_sfx.load_palette(self.lib)
        self.assertIn("palette not found", str(ctx.exception))
        self.assertIn(str(self.lib), str(ctx.exception))

    def test_generate_raises_named_error_when_palette_missing(self):
        with self.assertRaises(gen_sfx.LibraryError) as ctx:
            gen_sfx.generate(self.lib, env={"ELEVENLABS_API_KEY": "x"}, log=lambda *_: None)
        self.assertIn("palette not found", str(ctx.exception))

    def test_main_exits_1_when_palette_missing(self):
        rc = gen_sfx.main(["--library", str(self.lib), "--dry-run"])
        self.assertEqual(rc, 1)


class HomeLibraryTest(unittest.TestCase):
    """The library defaults to GASPOL_VIDEO_HOME; recipes stay in the plugin (GV-8 K4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        env = mock.patch.dict(os.environ, {"GASPOL_VIDEO_HOME": str(self.home),
                                           "ELEVENLABS_API_KEY": "k"})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.palette = self.root / "palette.json"
        self.palette.write_text(json.dumps({"recipes": [
            {"id": "pop-reveal", "prompt": "soft UI pop", "duration_s": 0.4}]}))

    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = gen_sfx.main(argv)
        return rc, out.getvalue()

    def test_default_library_is_home_and_recipes_come_from_the_flag(self):
        rc, out = self._run(["--recipes", str(self.palette), "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("would generate pop-reveal", out)
        self.assertTrue((self.home / "library" / "sfx").is_dir())

    def test_default_recipes_are_the_plugins_palette(self):
        first = json.loads(asset_home.recipes("sfx").read_text())["recipes"][0]["id"]
        rc, out = self._run(["--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn(f"would generate {first}", out)

    def test_home_catalog_makes_a_recipe_count_as_done(self):
        lib = asset_home.library("sfx")
        (lib / "catalog.json").write_text(json.dumps({"clips": [{"id": "pop-reveal"}]}))
        rc, out = self._run(["--recipes", str(self.palette), "--dry-run"])
        self.assertIn("library is complete", out)

    def test_explicit_library_reads_its_own_palette_and_ignores_home(self):
        lib = self.root / "custom"
        lib.mkdir()
        (lib / "palette.json").write_text(json.dumps({"recipes": [
            {"id": "custom-only", "prompt": "x", "duration_s": 1}]}))
        rc, out = self._run(["--library", str(lib), "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("would generate custom-only", out)
        self.assertFalse((self.home / "library").exists())

    def test_adopt_runs_before_a_real_run_but_not_a_dry_run(self):
        with mock.patch.object(gen_sfx.asset_home, "adopt", return_value=0) as adopt, \
                mock.patch.object(gen_sfx, "_request_sfx", side_effect=OSError("offline")):
            self._run(["--recipes", str(self.palette), "--dry-run"])
            adopt.assert_not_called()
            self._run(["--recipes", str(self.palette)])
            adopt.assert_called_once()
            self.assertEqual(adopt.call_args.args[0], "sfx")


class PluginPaletteTest(unittest.TestCase):
    NEW_IDS = ["sub-boom", "hit-heavy", "tail-air", "whoosh-fast",
               "riser-long", "glitch-hit", "stinger-up", "stinger-warn"]
    CATEGORIES = {"ambience", "emphasis", "machine", "motion", "snap", "tension", "vehicle"}

    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2] / "media" / "sfx" / "library" / "palette.json"
        cls.recipes = json.loads(path.read_text())["recipes"]
        cls.by_id = {r["id"]: r for r in cls.recipes}

    def test_new_recipes_present(self):
        for rid in self.NEW_IDS:
            self.assertIn(rid, self.by_id, f"missing recipe {rid}")

    def test_ids_unique(self):
        ids = [r["id"] for r in self.recipes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_recipe_shape_and_bounds(self):
        for r in self.recipes:
            for key in ("id", "prompt", "duration_s", "category"):
                self.assertIn(key, r, f"{r.get('id')} lacks {key}")
            self.assertIn(r["category"], self.CATEGORIES, r["id"])
            self.assertTrue(0.2 <= r["duration_s"] <= 15.0 if r["category"] in ("ambience", "machine") else 0.2 <= r["duration_s"] <= 5, r["id"])

    def test_new_recipes_duration_within_5s(self):
        for rid in self.NEW_IDS:
            self.assertTrue(0.2 <= self.by_id[rid]["duration_s"] <= 5, rid)

    def test_docs_example_stack_layers_exist(self):
        for rid in ("sub-boom", "hit-heavy", "tail-air", "riser-long"):
            self.assertIn(rid, self.by_id)


if __name__ == "__main__":
    unittest.main()
