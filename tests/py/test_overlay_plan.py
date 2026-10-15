import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.py import media
from tools import overlay_plan

FPS = 30
# "bukan cerita soal kebakaran besar di hutan kita" -> 0.5 s per word from 1.0 s.
SENTENCE = "bukan cerita soal kebakaran besar di hutan kita"
WORDS = [{"text": w, "start_ms": 1000 + i * 500, "end_ms": 1000 + i * 500 + 400}
         for i, w in enumerate(SENTENCE.split())]


def _cue(**over):
    cue = {"id": "c1", "words": "bukan cerita soal kebakaran", "lead": "bukan cerita soal",
           "keyword": "kebakaran", "fx": 1, "color": "white"}
    cue.update(over)
    return cue


def _scene(**over):
    scene = {"scene": "03", "clip": "clips/scene-03.mp4", "vo_layer": "s03-host",
             "fps": FPS, "width": 1080, "height": 1920, "cues": [_cue()]}
    scene.update(over)
    return scene


@media.requires_ffmpeg
class OverlayPlanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)
        (self.out / "shots").mkdir()
        (self.out / "clips").mkdir()
        (self.out / "vo").mkdir()
        (self.out / "work").mkdir()
        (self.out / "ref").mkdir()
        self.clip = self.out / "clips" / "scene-03.mp4"
        media.make_clip(self.clip, seconds=10, fps=FPS, size="64x48", audio=False)
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": WORDS}])

    def write_manifest(self, items):
        (self.out / "vo" / "vo-manifest.json").write_text(json.dumps({"items": items}))

    def write_plan(self, *scenes):
        (self.out / "work" / "overlay-plan.json").write_text(
            json.dumps({"scenes": list(scenes)}))

    def make_mask(self, frames=3, sha=None):
        d = self.out / ".tmp" / "mask-03"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(1, frames + 1):
            (d / f"{i:05d}.png").write_bytes(b"png%d" % i)
        sha = sha or hashlib.sha256(self.clip.read_bytes()).hexdigest()
        (d / "source.json").write_text(json.dumps(
            {"clip_sha256": sha, "frames": frames, "fps": FPS, "w": 64, "h": 48,
             "feather_px": 4, "model_sha256": "m"}))

    def run_plan(self, *scenes, scene=None):
        self.write_plan(*scenes)
        return overlay_plan.run(self.out, scene=scene)

    def refused(self, *scenes):
        with self.assertRaises(overlay_plan.OverlayPlanError) as cm:
            self.run_plan(*scenes)
        return "\n".join(cm.exception.problems)

    def result(self, scene="03"):
        p = self.out / "shots" / "src" / "shots" / f"overlay-{scene}.json"
        return json.loads(p.read_text())

    def test_resolves_one_anchor_to_frames(self):
        self.run_plan(_scene())
        res = self.result()
        cue = res["cues"][0]
        # words 0..3 -> first starts 1.0 s, last (index 3) ends 2.9 s.
        self.assertEqual(cue["inF"], round((1.0 - 0.10) * FPS))
        self.assertEqual(cue["keyF"], round(2.5 * FPS))
        self.assertEqual(cue["outF"], round((2.9 + 0.3) * FPS))
        self.assertEqual(res["clip"], "overlay/03/clip.mp4")
        self.assertIsNone(res["mask"])
        self.assertEqual(res["durationInFrames"], 10 * FPS)
        self.assertEqual((res["fps"], res["width"], res["height"]), (FPS, 1080, 1920))
        self.assertEqual(cue["id"], "c1")

    def test_anchor_mid_layer(self):
        self.run_plan(_scene(cues=[_cue(words="besar di hutan", lead="besar di",
                                        keyword="hutan")]))
        cue = self.result()["cues"][0]
        self.assertEqual(cue["inF"], round((3.0 - 0.10) * FPS))
        self.assertEqual(cue["keyF"], round(4.0 * FPS))

    def test_repeated_anchor_picks_one_after_previous_cue(self):
        words = [{"text": w, "start_ms": i * 500, "end_ms": i * 500 + 400}
                 for i, w in enumerate("kita sama kita sama".split())]
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": words}])
        c1 = _cue(id="c1", words="kita sama", lead="kita", keyword="sama", hold_s=0)
        c2 = _cue(id="c2", words="kita sama", lead="kita", keyword="sama")
        self.run_plan(_scene(cues=[c1, c2]))
        cues = self.result()["cues"]
        self.assertEqual(cues[0]["keyF"], round(0.5 * FPS))
        self.assertEqual(cues[1]["keyF"], round(1.5 * FPS))

    def test_anchor_missing_refused(self):
        msg = self.refused(_scene(cues=[_cue(words="tidak ada disini", lead="tidak",
                                             keyword="ada")]))
        self.assertIn("scene 03 cue c1:", msg)
        self.assertIn("not found", msg)

    def test_punctuation_and_case_match(self):
        words = [{"text": t, "start_ms": i * 500, "end_ms": i * 500 + 400}
                 for i, t in enumerate(["Bukan,", "CERITA", "soal.", "Kebakaran!"])]
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": words}])
        self.run_plan(_scene())
        self.assertEqual(self.result()["cues"][0]["keyF"], round(1.5 * FPS))

    def test_keyword_not_in_words_refused(self):
        msg = self.refused(_scene(cues=[_cue(keyword="banjir")]))
        self.assertIn("keyword", msg)

    def test_key_words_times_a_keyword_that_is_not_spoken_verbatim(self):
        # Shown "1 dari 3" while the voice says "soal"; the number is never spoken as a digit.
        self.run_plan(_scene(cues=[_cue(keyword="1 dari 3", key_words="soal", fx=3)]))
        cue = self.result()["cues"][0]
        self.assertEqual(cue["keyF"], round(2.0 * FPS))
        self.assertEqual(cue["keyword"], "1 dari 3")

    def test_output_writes_defaults_the_composition_relies_on(self):
        # A cue with no layer/pos validated as "front" but was never drawn (the template
        # matches layer exactly, and reads pos.x).
        (self.out / "ref" / "a.png").write_bytes(b"png")
        self.run_plan(_scene(cues=[_cue(panels=[{"src": "ref:a.png", "x": 0, "y": 0,
                                                 "w": 10, "h": 10}])]))
        cue = self.result()["cues"][0]
        self.assertEqual((cue["layer"], cue["fx"], cue["color"], cue["script"], cue["source"]),
                         ("front", 1, "white", False, ""))
        self.assertEqual(cue["pos"], {"anchor": "top", "x": None, "y": None})
        self.assertIsNone(cue["icon"])
        self.assertEqual((cue["panels"][0]["layer"], cue["panels"][0]["kind"],
                          cue["panels"][0]["caption"]), ("front", "image", ""))

    def test_pos_without_anchor_defaults_to_top(self):
        self.run_plan(_scene(cues=[_cue(pos={"x": 500, "y": 300})]))
        self.assertEqual(self.result()["cues"][0]["pos"], {"anchor": "top", "x": 500, "y": 300})

    def test_unknown_pos_anchor_refused(self):
        msg = self.refused(_scene(cues=[_cue(pos={"anchor": "bottom"})]))
        self.assertIn("pos anchor", msg)

    def test_output_cue_always_carries_the_three_media_lists(self):
        # KineticOverlay maps over all three; a missing key crashed the first real render.
        self.run_plan(_scene())
        cue = self.result()["cues"][0]
        self.assertEqual((cue["panels"], cue["bubbles"], cue["carousel"]), ([], [], []))

    def test_key_words_not_inside_words_refused(self):
        msg = self.refused(_scene(cues=[_cue(keyword="1", key_words="banjir", fx=3)]))
        self.assertIn("key_words 'banjir' is not inside words", msg)

    def test_vo_offset_shifts_times(self):
        self.run_plan(_scene(vo_offset_s=2.0))
        cue = self.result()["cues"][0]
        self.assertEqual(cue["inF"], round((3.0 - 0.10) * FPS))
        self.assertEqual(cue["keyF"], round(4.5 * FPS))
        self.assertEqual(cue["outF"], round((4.9 + 0.3) * FPS))

    def test_in_clamps_to_zero(self):
        words = [{"text": w, "start_ms": 20 + i * 500, "end_ms": 420 + i * 500}
                 for i, w in enumerate(SENTENCE.split())]
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": words}])
        self.run_plan(_scene())
        self.assertEqual(self.result()["cues"][0]["inF"], 0)

    def test_hold_s_custom(self):
        self.run_plan(_scene(cues=[_cue(hold_s=1.0)]))
        self.assertEqual(self.result()["cues"][0]["outF"], round(3.9 * FPS))

    def test_overlap_over_tenth_refused(self):
        c1 = _cue(id="c1", hold_s=1.0)  # out 3.9
        c2 = _cue(id="c2", words="besar di hutan", lead="besar", keyword="hutan")  # in 2.9
        msg = self.refused(_scene(cues=[c1, c2]))
        self.assertIn("scene 03 cue c2:", msg)
        self.assertIn("overlap", msg)

    def test_overlap_within_tenth_allowed(self):
        c1 = _cue(id="c1", hold_s=0.58)  # out 3.48, next in 3.4 -> 0.08 overlap
        c2 = _cue(id="c2", words="di hutan", lead="di", keyword="hutan")  # in 3.4
        self.run_plan(_scene(cues=[c1, c2]))
        self.assertEqual(len(self.result()["cues"]), 2)

    def test_out_past_clip_refused(self):
        words = [{"text": w, "start_ms": 9000 + i * 500, "end_ms": 9400 + i * 500}
                 for i, w in enumerate(SENTENCE.split())]
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": words}])
        msg = self.refused(_scene())
        self.assertIn("clip", msg)

    def test_unknown_enums_refused(self):
        for field, value in [("fx", 9), ("fx", 5), ("fx", 6), ("color", "red"),
                             ("layer", "middle"), ("icon", "unicorn")]:
            with self.subTest(field=field, value=value):
                msg = self.refused(_scene(cues=[_cue(**{field: value})]))
                self.assertIn(field, msg)

    def test_unknown_panel_kind_and_prefix_refused(self):
        panel = {"src": "web:x.png", "kind": "gif", "x": 0, "y": 0, "w": 10, "h": 10}
        msg = self.refused(_scene(cues=[_cue(panels=[panel])]))
        self.assertIn("prefix", msg)
        self.assertIn("kind", msg)

    def test_fx3_needs_digit(self):
        msg = self.refused(_scene(cues=[_cue(fx=3)]))
        self.assertIn("digit", msg)

    def test_fx3_with_digit_ok(self):
        words = [{"text": t, "start_ms": i * 500, "end_ms": i * 500 + 400}
                 for i, t in enumerate(["ada", "40", "titik"])]
        self.write_manifest([{"id": "s03-host", "scene": "03", "words": words}])
        self.run_plan(_scene(cues=[_cue(words="ada 40", lead="ada", keyword="40", fx=3)]))
        self.assertEqual(self.result()["cues"][0]["fx"], 3)

    def test_icon_accepted(self):
        for icon in overlay_plan.ICONS:
            self.run_plan(_scene(cues=[_cue(icon=icon)]))
        self.assertEqual(overlay_plan.ICONS,
                         ("fire", "gavel", "chart", "cloud", "question", "arrow", "circle"))

    def test_missing_user_and_ref_files_refused(self):
        panel = {"src": "user:photos/none.jpg", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1}
        bubble = {"src": "ref:none.png", "label": "x", "x": 0, "y": 0, "d": 5}
        msg = self.refused(_scene(cues=[_cue(panels=[panel], bubbles=[bubble])]))
        self.assertIn("none.jpg", msg)
        self.assertIn("none.png", msg)
        self.assertIn("scene 03 cue c1:", msg)

    def test_bad_remotion_name_refused(self):
        for name in ("lower", "Has-Dash", "1Bad", ""):
            with self.subTest(name=name):
                panel = {"src": "remotion:" + name, "kind": "image",
                         "x": 0, "y": 0, "w": 1, "h": 1}
                msg = self.refused(_scene(cues=[_cue(panels=[panel])]))
                self.assertIn("remotion", msg)

    def test_remotion_src_passes_through(self):
        panel = {"src": "remotion:MapShot", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1}
        self.run_plan(_scene(cues=[_cue(panels=[panel])]))
        self.assertEqual(self.result()["cues"][0]["panels"][0]["src"], {"remotion": "MapShot"})

    def test_behind_without_mask_refused(self):
        msg = self.refused(_scene(cues=[_cue(layer="behind")]))
        self.assertIn("run tools/person_mask.py first", msg)

    def test_behind_panel_without_mask_refused(self):
        panel = {"src": "remotion:MapShot", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1,
                 "layer": "behind"}
        msg = self.refused(_scene(cues=[_cue(panels=[panel])]))
        self.assertIn("run tools/person_mask.py first", msg)

    def test_mask_stale_or_incomplete_refused(self):
        self.make_mask(sha="0" * 64)
        self.assertIn("person_mask.py", self.refused(_scene(cues=[_cue(layer="behind")])))
        self.make_mask(frames=3)
        (self.out / ".tmp" / "mask-03" / "00003.png").unlink()
        self.assertIn("person_mask.py", self.refused(_scene(cues=[_cue(layer="behind")])))

    def test_behind_with_valid_mask_stages_frames(self):
        self.make_mask(frames=3)
        self.run_plan(_scene(cues=[_cue(layer="behind")]))
        res = self.result()
        self.assertEqual(res["mask"], "overlay/03/mask/")
        staged = self.out / "shots" / "public" / "overlay" / "03" / "mask"
        self.assertEqual(sorted(p.name for p in staged.iterdir()),
                         ["00001.png", "00002.png", "00003.png"])

    def test_empty_cues_refused(self):
        self.assertIn("no cues", self.refused(_scene(cues=[])))

    def test_missing_vo_layer_refused(self):
        msg = self.refused(_scene(vo_layer="nope"))
        self.assertIn("nope", msg)

    def test_words_file_source(self):
        (self.out / "work" / "asr-03.json").write_text(json.dumps(WORDS))
        scene = _scene(words_file="work/asr-03.json")
        del scene["vo_layer"]
        self.run_plan(scene)
        self.assertEqual(self.result()["cues"][0]["keyF"], round(2.5 * FPS))

    def test_words_file_missing_exits_missing_input(self):
        scene = _scene(words_file="work/none.json")
        del scene["vo_layer"]
        self.write_plan(scene)
        with self.assertRaises(overlay_plan.MissingInput) as cm:
            overlay_plan.run(self.out)
        self.assertIn("none.json", str(cm.exception))

    def test_both_or_neither_word_source_refused(self):
        both = _scene(words_file="work/asr-03.json")
        self.assertIn("exactly one", self.refused(both))
        neither = _scene()
        del neither["vo_layer"]
        self.assertIn("exactly one", self.refused(neither))

    def test_missing_manifest_exits_missing_input(self):
        (self.out / "vo" / "vo-manifest.json").unlink()
        self.write_plan(_scene())
        with self.assertRaises(overlay_plan.MissingInput) as cm:
            overlay_plan.run(self.out)
        self.assertIn("vo-manifest.json", str(cm.exception))

    def test_missing_plan_exits_missing_input(self):
        with self.assertRaises(overlay_plan.MissingInput) as cm:
            overlay_plan.run(self.out)
        self.assertIn("overlay-plan.json", str(cm.exception))

    def test_missing_shots_refused(self):
        (self.out / "shots").rmdir()
        msg = self.refused(_scene())
        self.assertIn("scaffold the Remotion workspace first", msg)

    def test_all_problems_reported_in_one_run(self):
        msg = self.refused(_scene(cues=[_cue(id="a", fx=9),
                                        _cue(id="b", color="red"),
                                        _cue(id="c", layer="behind")]))
        for cid in ("cue a:", "cue b:", "cue c:"):
            self.assertIn(cid, msg)

    def test_staging_and_idempotent(self):
        media_file = self.out / "ref" / "map.png"
        media_file.write_bytes(b"map")
        user = self.out / "photos"
        user.mkdir()
        (user / "w.jpg").write_bytes(b"jpg")
        panel = {"src": "ref:map.png", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1}
        bubble = {"src": "user:photos/w.jpg", "label": "x", "x": 0, "y": 0, "d": 5}
        scene = _scene(cues=[_cue(panels=[panel], bubbles=[bubble],
                                  carousel=[{"src": "ref:map.png", "label": "a"}])])
        self.make_mask(frames=2)
        scene["cues"][0]["layer"] = "behind"
        self.run_plan(scene)
        pub = self.out / "shots" / "public" / "overlay" / "03"
        files = sorted(str(p.relative_to(pub)) for p in pub.rglob("*") if p.is_file())
        self.assertEqual(files, ["clip.mp4", "map.png", "mask/00001.png", "mask/00002.png",
                                 "w.jpg"])
        cue = self.result()["cues"][0]
        self.assertEqual(cue["panels"][0]["src"], "overlay/03/map.png")
        self.assertEqual(cue["bubbles"][0]["src"], "overlay/03/w.jpg")
        self.assertEqual(cue["carousel"][0]["src"], "overlay/03/map.png")
        first = (self.out / "shots" / "src" / "shots" / "overlay-03.json").read_bytes()
        msgs = overlay_plan.run(self.out)
        self.assertEqual((self.out / "shots" / "src" / "shots" / "overlay-03.json").read_bytes(),
                         first)
        self.assertEqual(msgs, ["overlay 03: 1 cues, 5 files staged"])

    def test_basename_collision_refused(self):
        (self.out / "ref" / "a.png").write_bytes(b"1")
        (self.out / "photos").mkdir()
        (self.out / "photos" / "a.png").write_bytes(b"2")
        p1 = {"src": "ref:a.png", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1}
        p2 = {"src": "user:photos/a.png", "kind": "image", "x": 0, "y": 0, "w": 1, "h": 1}
        self.assertIn("a.png", self.refused(_scene(cues=[_cue(panels=[p1, p2])])))

    def test_scene_filter(self):
        s2 = copy.deepcopy(_scene(scene="04", clip="clips/scene-03.mp4", vo_layer="s03-host"))
        self.write_plan(_scene(), s2)
        msgs = overlay_plan.run(self.out, scene="04")
        self.assertEqual(len(msgs), 1)
        self.assertTrue(msgs[0].startswith("overlay 04:"))
        self.assertFalse((self.out / "shots" / "src" / "shots" / "overlay-03.json").exists())

    def test_cli_exit_codes(self):
        self.write_plan(_scene())
        self.assertEqual(overlay_plan.main([str(self.out)]), 0)
        self.write_plan(_scene(cues=[_cue(fx=9)]))
        self.assertEqual(overlay_plan.main([str(self.out)]), 1)
        (self.out / "work" / "overlay-plan.json").unlink()
        self.assertEqual(overlay_plan.main([str(self.out)]), 2)


if __name__ == "__main__":
    unittest.main()
