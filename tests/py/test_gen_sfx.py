import json
import tempfile
import unittest
from pathlib import Path

from tools import gen_sfx


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


if __name__ == "__main__":
    unittest.main()
