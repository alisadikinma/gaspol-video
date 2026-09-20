import json
import tempfile
import unittest
from pathlib import Path

from tools import gen_captions
from tools.burn_subs import StyleError

# The brand.json these projects actually ship (measured 2026-09-20):
#   ink/background 16.41, background/accent 4.21, ink/accent 3.90.
# background clears the 3:1 highlight-text floor and ink does not, so this is the
# reference case for "background" winning the token choice.
REAL_SHIPPED_BRAND = {
    "background": "#FAF8F4",
    "ink": "#1A1A1A",
    "inkSoft": "#5A5A5A",
    "accent": "#6366F1",
    "displayFont": "Inter, system-ui, sans-serif",
    "bodyFont": "Inter, system-ui, sans-serif",
}

# Same ink/background as above but a light accent close to background's own luminance:
# ink/accent 13.18, background/accent 1.24 — ink wins this time.
INK_WINS_BRAND = dict(REAL_SHIPPED_BRAND, accent="#E0E0E0")

# ink/background 4.55 (clears 4.5, barely) with an accent sitting at the luminance
# midpoint between them: ink/accent 2.14, background/accent 2.13 — neither reaches 3:1.
BOTH_FAIL_BRAND = {
    "background": "#A0A0A0",
    "ink": "#373737",
    "inkSoft": "#5A5A5A",
    "accent": "#686868",
    "displayFont": "Inter, system-ui, sans-serif",
    "bodyFont": "Inter, system-ui, sans-serif",
}


class CaptionContrastTest(unittest.TestCase):
    def test_refuses_brand_whose_ink_and_background_are_below_4_5(self):
        brand = dict(REAL_SHIPPED_BRAND, background="#1F1F1F")  # near-black on near-black ink
        with self.assertRaises(StyleError):
            gen_captions.check_brand_contrast(brand)

    def test_accepts_the_real_shipped_brand_and_picks_background(self):
        token = gen_captions.check_brand_contrast(REAL_SHIPPED_BRAND)
        self.assertEqual(token, "background")

    def test_picks_ink_when_ink_scores_higher_against_accent(self):
        token = gen_captions.check_brand_contrast(INK_WINS_BRAND)
        self.assertEqual(token, "ink")

    def test_refuses_when_neither_ink_nor_background_reaches_3_1_against_accent(self):
        with self.assertRaises(StyleError):
            gen_captions.check_brand_contrast(BOTH_FAIL_BRAND)


class BuildCaptionPlanBrandWiringTest(unittest.TestCase):
    """work/caption-plan.json must carry style.highlight_text_token when a brand is
    given, so Captions.template.tsx reads the decision instead of making one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "work").mkdir()
        (self.project / "vo").mkdir()
        (self.project / "work" / "audio-plan.json").write_text(json.dumps({
            "scenes": [
                {"scene": 1, "layers": [
                    {"kind": "narration", "at_s": 0.0, "text": "Halo dunia.",
                     "out": "vo/scene-01-narr.mp3"},
                ]},
            ],
        }))
        (self.project / "vo" / "vo-manifest.json").write_text(json.dumps({
            "items": [
                {"id": "scene-01-narr", "words": [
                    {"text": "Halo", "start_ms": 0, "end_ms": 300},
                    {"text": "dunia.", "start_ms": 300, "end_ms": 700},
                ]},
            ],
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_carries_highlight_text_token_when_brand_given(self):
        plan = gen_captions.build_caption_plan(self.project, keyterms=[], brand=REAL_SHIPPED_BRAND)
        self.assertEqual(plan["style"]["highlight_text_token"], "background")

    def test_plan_has_no_highlight_text_token_when_no_brand_given(self):
        plan = gen_captions.build_caption_plan(self.project, keyterms=[])
        self.assertNotIn("highlight_text_token", plan["style"])


if __name__ == "__main__":
    unittest.main()
