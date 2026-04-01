"""Non-Blender tests for the template mesh pipeline.

These tests validate path resolution, config propagation, and constants
without requiring Blender or importing bpy.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.humanoid.template_mesh import CARTOON_MALE_GLB, _TEMPLATE_DIR
from generators.humanoid.presets import resolve_config


class TestTemplatePaths(unittest.TestCase):

    def test_cartoon_male_glb_exists(self):
        self.assertTrue(
            os.path.isfile(CARTOON_MALE_GLB),
            f"Cartoon_Male.glb not found at: {CARTOON_MALE_GLB}",
        )

    def test_cartoon_male_glb_is_nonzero(self):
        size = os.path.getsize(CARTOON_MALE_GLB)
        self.assertGreater(size, 1000, "Cartoon_Male.glb is suspiciously small")

    def test_template_dir_exists(self):
        self.assertTrue(os.path.isdir(_TEMPLATE_DIR))


class TestResolveConfigTemplatePropagation(unittest.TestCase):
    """Check that use_template and lod survive resolve_config unchanged."""

    def test_use_template_true_by_default(self):
        cfg = resolve_config()
        self.assertTrue(cfg["use_template"])

    def test_use_template_true_propagates(self):
        cfg = resolve_config(use_template=True, lod="mid")
        self.assertTrue(cfg["use_template"])
        self.assertEqual(cfg["lod"], "mid")

    def test_lod_default_is_mid(self):
        cfg = resolve_config(use_template=True)
        self.assertEqual(cfg["lod"], "low")

    def test_overrides_can_set_use_template(self):
        cfg = resolve_config(overrides={"use_template": True, "lod": "very_low"})
        self.assertTrue(cfg["use_template"])
        self.assertEqual(cfg["lod"], "very_low")

    def test_all_lods_accepted(self):
        for lod in ("very_low", "low", "mid"):
            cfg = resolve_config(use_template=True, lod=lod)
            self.assertEqual(cfg["lod"], lod)

    def test_skin_tone_default_is_tan(self):
        cfg = resolve_config()
        # resolve_config converts "tan" → RGBA tuple
        from generators.humanoid.presets import SKIN_TONES
        self.assertEqual(cfg["skin_tone"], SKIN_TONES["tan"])


class TestSkinTones(unittest.TestCase):
    """Validate skin tone RGBA values."""

    def test_tan_is_defined(self):
        from generators.humanoid.presets import SKIN_TONES
        self.assertIn("tan", SKIN_TONES)

    def test_all_skin_tones_are_rgba(self):
        from generators.humanoid.presets import SKIN_TONES
        for name, rgba in SKIN_TONES.items():
            self.assertEqual(len(rgba), 4, f"{name} is not RGBA")
            for ch in rgba:
                self.assertGreaterEqual(ch, 0.0)
                self.assertLessEqual(ch, 1.0)


class TestClothingTypes(unittest.TestCase):
    """Validate the clothing module constants used by template_mesh."""

    def test_expected_types_present(self):
        from generators.humanoid.clothing import CLOTHING_TYPES
        for t in ("none", "short_sleeve", "long_sleeve", "v_neck", "shorts", "jeans"):
            self.assertIn(t, CLOTHING_TYPES)

    def test_default_colors_cover_all_types(self):
        from generators.humanoid.clothing import CLOTHING_TYPES, CLOTHING_DEFAULT_COLORS, CLOTHING_COLORS
        for t in CLOTHING_TYPES:
            if t == "none":
                continue
            default_name = CLOTHING_DEFAULT_COLORS.get(t)
            self.assertIsNotNone(default_name, f"{t} has no default color")
            self.assertIn(default_name, CLOTHING_COLORS, f"{t} default color '{default_name}' not in CLOTHING_COLORS")

    def test_resolve_clothing_rgba_returns_tuple(self):
        from generators.humanoid.clothing import resolve_clothing_rgba, CLOTHING_TYPES
        for t in CLOTHING_TYPES:
            if t == "none":
                continue
            rgba = resolve_clothing_rgba(t)
            self.assertEqual(len(rgba), 4)


if __name__ == "__main__":
    unittest.main()
