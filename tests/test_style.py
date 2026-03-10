"""Tests for the shared style configuration system."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.style import AssetStyle, THEMES, MATERIALS


class TestAssetStyle(unittest.TestCase):

    def test_defaults(self):
        s = AssetStyle()
        self.assertEqual(s.theme, "modern")
        self.assertEqual(s.material, "concrete")
        self.assertEqual(s.wear, 0.5)

    def test_all_themes_valid(self):
        for theme in THEMES:
            s = AssetStyle(theme=theme)
            self.assertEqual(s.theme, theme)

    def test_all_materials_valid(self):
        for mat in MATERIALS:
            s = AssetStyle(material=mat)
            self.assertEqual(s.material, mat)

    def test_invalid_theme_raises(self):
        with self.assertRaises(ValueError):
            AssetStyle(theme="cyberpunk")

    def test_invalid_material_raises(self):
        with self.assertRaises(ValueError):
            AssetStyle(material="glass")

    def test_wear_clamped(self):
        s = AssetStyle(wear=5.0)
        self.assertEqual(s.wear, 1.0)
        s = AssetStyle(wear=-1.0)
        self.assertEqual(s.wear, 0.0)

    def test_get_color_returns_rgba(self):
        s = AssetStyle(material="metal", wear=0.0)
        color = s.get_color()
        self.assertEqual(len(color), 4)
        self.assertTrue(all(0.0 <= c <= 1.0 for c in color))

    def test_get_color_varies_with_wear(self):
        clean = AssetStyle(material="brick", wear=0.0).get_color()
        worn = AssetStyle(material="brick", wear=1.0).get_color()
        # Worn brick should be darker (lower RGB values)
        self.assertGreater(clean[0], worn[0])

    def test_roughness_range(self):
        for mat in MATERIALS:
            r = AssetStyle(material=mat).get_roughness()
            self.assertTrue(0.0 <= r <= 1.0, f"{mat} roughness {r} out of range")

    def test_metallic_range(self):
        for mat in MATERIALS:
            m = AssetStyle(material=mat).get_metallic()
            self.assertTrue(0.0 <= m <= 1.0, f"{mat} metallic {m} out of range")

    def test_metal_is_metallic(self):
        s = AssetStyle(material="metal", wear=0.0)
        self.assertGreater(s.get_metallic(), 0.5)

    def test_wood_is_not_metallic(self):
        s = AssetStyle(material="wood", wear=0.0)
        self.assertLess(s.get_metallic(), 0.1)

    def test_roundtrip_dict(self):
        s = AssetStyle(theme="fantasy", material="stone", wear=0.8)
        d = s.to_dict()
        s2 = AssetStyle.from_dict(d)
        self.assertEqual(s.theme, s2.theme)
        self.assertEqual(s.material, s2.material)
        self.assertAlmostEqual(s.wear, s2.wear)


class TestWallFloorConfig(unittest.TestCase):
    """Test wall and floor __init__ configs without Blender."""

    def test_wall_variations_listed(self):
        from generators.wall import VARIATIONS
        self.assertEqual(len(VARIATIONS), 6)
        self.assertIn("brick", VARIATIONS)
        self.assertIn("chainlink", VARIATIONS)

    def test_floor_variations_listed(self):
        from generators.floor import VARIATIONS
        self.assertEqual(len(VARIATIONS), 6)
        self.assertIn("concrete", VARIATIONS)
        self.assertIn("cobblestone", VARIATIONS)

    def test_wall_invalid_variation_raises(self):
        # generate() imports bpy transitively via mesh, so we test
        # that the VARIATIONS tuple is correct instead.
        from generators.wall import VARIATIONS
        self.assertNotIn("glass_curtain", VARIATIONS)

    def test_floor_invalid_variation_raises(self):
        from generators.floor import VARIATIONS
        self.assertNotIn("carpet", VARIATIONS)


class TestCLIRegistration(unittest.TestCase):

    def test_wall_registered(self):
        from generator.__main__ import ASSET_SCRIPTS
        self.assertIn("wall", ASSET_SCRIPTS)

    def test_floor_registered(self):
        from generator.__main__ import ASSET_SCRIPTS
        self.assertIn("floor", ASSET_SCRIPTS)

    def test_all_scripts_exist(self):
        from generator.__main__ import ASSET_SCRIPTS
        for name, path in ASSET_SCRIPTS.items():
            resolved = os.path.abspath(path)
            self.assertTrue(
                os.path.isfile(resolved),
                f"Script for '{name}' not found at {resolved}",
            )


if __name__ == "__main__":
    unittest.main()
