"""Tests for character presets and body configuration."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.humanoid.presets import (
    PRESETS, BUILDS, SKIN_TONES,
    get_preset_names, get_build_names, get_skin_tone_names,
    resolve_config,
)
from generators.humanoid.hair import (
    HAIR_STYLES, HAIR_COLORS, HAIR_BUILDERS,
    get_hair_style_names, get_hair_color_names,
)


class TestPresets(unittest.TestCase):

    def test_all_presets_have_required_keys(self):
        required = {
            "height", "shoulder_width", "hip_width", "head_size",
            "arm_length", "leg_length", "torso_length", "neck_length",
            "hand_size", "foot_length", "foot_width",
            "limb_thickness", "torso_depth",
        }
        for name, preset in PRESETS.items():
            for key in required:
                self.assertIn(key, preset, f"Preset '{name}' missing '{key}'")

    def test_preset_count(self):
        self.assertEqual(len(PRESETS), 6)

    def test_preset_names_sorted(self):
        names = get_preset_names()
        self.assertEqual(names, sorted(names))

    def test_all_heights_positive(self):
        for name, preset in PRESETS.items():
            self.assertGreater(preset["height"], 0, f"{name} height <= 0")

    def test_brute_taller_than_child(self):
        self.assertGreater(PRESETS["brute"]["height"], PRESETS["child"]["height"])

    def test_brute_wider_shoulders_than_slender(self):
        self.assertGreater(
            PRESETS["brute"]["shoulder_width"],
            PRESETS["slender"]["shoulder_width"],
        )

    def test_child_larger_head_ratio(self):
        """Child should have a proportionally larger head relative to height."""
        child_ratio = PRESETS["child"]["head_size"] / PRESETS["child"]["height"]
        avg_ratio = PRESETS["average"]["head_size"] / PRESETS["average"]["height"]
        self.assertGreater(child_ratio, avg_ratio)


class TestBuilds(unittest.TestCase):

    def test_build_count(self):
        self.assertEqual(len(BUILDS), 4)

    def test_average_build_is_empty(self):
        self.assertEqual(BUILDS["average"], {})

    def test_heavy_wider_than_lean(self):
        heavy = BUILDS["heavy"]
        lean = BUILDS["lean"]
        self.assertGreater(
            heavy.get("shoulder_width", 1.0),
            lean.get("shoulder_width", 1.0),
        )

    def test_build_names_sorted(self):
        names = get_build_names()
        self.assertEqual(names, sorted(names))


class TestSkinTones(unittest.TestCase):

    def test_all_tones_are_rgba(self):
        for name, color in SKIN_TONES.items():
            self.assertEqual(len(color), 4, f"{name} not RGBA")
            self.assertTrue(all(0 <= c <= 1 for c in color),
                            f"{name} has out-of-range channel")

    def test_has_game_tones(self):
        for name in ("zombie", "orc", "frost", "ember", "shadow"):
            self.assertIn(name, SKIN_TONES)

    def test_tone_names_sorted(self):
        names = get_skin_tone_names()
        self.assertEqual(names, sorted(names))


class TestResolveConfig(unittest.TestCase):

    def test_default_resolve(self):
        cfg = resolve_config()
        self.assertIn("height", cfg)
        self.assertIn("skin_tone", cfg)
        self.assertEqual(cfg["height"], PRESETS["average"]["height"])

    def test_preset_applies(self):
        cfg = resolve_config(preset="tall")
        self.assertEqual(cfg["height"], PRESETS["tall"]["height"])

    def test_build_modifies_proportions(self):
        base = resolve_config(preset="average", build="average")
        heavy = resolve_config(preset="average", build="heavy")
        self.assertGreater(heavy["shoulder_width"], base["shoulder_width"])

    def test_skin_tone_by_name(self):
        cfg = resolve_config(skin_tone="orc")
        self.assertEqual(cfg["skin_tone"], SKIN_TONES["orc"])

    def test_skin_tone_custom_tuple(self):
        custom = (0.5, 0.3, 0.2, 1.0)
        cfg = resolve_config(skin_tone=custom)
        self.assertEqual(cfg["skin_tone"], custom)

    def test_overrides_take_priority(self):
        cfg = resolve_config(preset="short", overrides={"height": 3.0})
        self.assertEqual(cfg["height"], 3.0)

    def test_invalid_preset_raises(self):
        with self.assertRaises(ValueError):
            resolve_config(preset="giant")

    def test_invalid_build_raises(self):
        with self.assertRaises(ValueError):
            resolve_config(build="muscular")

    def test_invalid_skin_tone_raises(self):
        with self.assertRaises(ValueError):
            resolve_config(skin_tone="neon_pink")

    def test_randomize_produces_variation(self):
        cfg1 = resolve_config(randomize=True, seed=42)
        cfg2 = resolve_config(randomize=True, seed=99)
        # With different seeds, at least some proportion should differ
        diffs = [abs(cfg1[k] - cfg2[k]) for k in ("height", "shoulder_width", "leg_length")]
        self.assertTrue(any(d > 0.001 for d in diffs))

    def test_same_seed_reproducible(self):
        cfg1 = resolve_config(randomize=True, seed=42)
        cfg2 = resolve_config(randomize=True, seed=42)
        for key in ("height", "shoulder_width", "leg_length"):
            self.assertAlmostEqual(cfg1[key], cfg2[key], places=10)

    def test_resolved_config_has_limb_thickness(self):
        cfg = resolve_config()
        self.assertIn("limb_thickness", cfg)
        self.assertGreater(cfg["limb_thickness"], 0)

    def test_resolved_config_has_torso_depth(self):
        cfg = resolve_config()
        self.assertIn("torso_depth", cfg)
        self.assertGreater(cfg["torso_depth"], 0)


class TestHairStyles(unittest.TestCase):

    def test_style_count(self):
        # 6 styles + "none"
        self.assertEqual(len(HAIR_STYLES), 7)

    def test_all_non_none_styles_have_builders(self):
        for style in HAIR_STYLES:
            if style != "none":
                self.assertIn(style, HAIR_BUILDERS, f"No builder for '{style}'")

    def test_expected_styles_exist(self):
        for style in ("buzzed", "short", "spiky", "long", "mohawk", "ponytail"):
            self.assertIn(style, HAIR_STYLES)

    def test_none_not_in_builders(self):
        self.assertNotIn("none", HAIR_BUILDERS)

    def test_style_names_list(self):
        names = get_hair_style_names()
        self.assertIn("none", names)
        self.assertIn("mohawk", names)

    def test_builders_are_callable(self):
        for name, builder in HAIR_BUILDERS.items():
            self.assertTrue(callable(builder), f"Builder '{name}' not callable")


class TestHairColors(unittest.TestCase):

    def test_all_colors_are_rgba(self):
        for name, color in HAIR_COLORS.items():
            self.assertEqual(len(color), 4, f"{name} not RGBA")
            self.assertTrue(all(0 <= c <= 1 for c in color),
                            f"{name} has out-of-range channel")

    def test_natural_colors_exist(self):
        for name in ("black", "brown", "blonde", "red", "white", "grey"):
            self.assertIn(name, HAIR_COLORS)

    def test_fantasy_colors_exist(self):
        for name in ("blue", "green", "purple", "pink"):
            self.assertIn(name, HAIR_COLORS)

    def test_color_names_sorted(self):
        names = get_hair_color_names()
        self.assertEqual(names, sorted(names))

    def test_color_count(self):
        self.assertEqual(len(HAIR_COLORS), 13)


class TestResolveConfigHair(unittest.TestCase):

    def test_default_hair_style_is_none(self):
        cfg = resolve_config()
        self.assertEqual(cfg["hair_style"], "none")

    def test_hair_style_set(self):
        cfg = resolve_config(hair_style="mohawk")
        self.assertEqual(cfg["hair_style"], "mohawk")

    def test_hair_color_set_by_name(self):
        cfg = resolve_config(hair_color="blonde")
        self.assertEqual(cfg["hair_color"], "blonde")

    def test_hair_color_custom_tuple(self):
        custom = (1.0, 0.0, 0.5, 1.0)
        cfg = resolve_config(hair_color=custom)
        self.assertEqual(cfg["hair_color"], custom)

    def test_invalid_hair_style_raises(self):
        with self.assertRaises(ValueError):
            resolve_config(hair_style="afro")

    def test_invalid_hair_color_raises(self):
        with self.assertRaises(ValueError):
            resolve_config(hair_color="neon_yellow")

    def test_hair_override_via_overrides(self):
        cfg = resolve_config(hair_style="short",
                             overrides={"hair_style": "spiky"})
        self.assertEqual(cfg["hair_style"], "spiky")


class TestHumanoidInitPresets(unittest.TestCase):
    """Test that humanoid __init__ exports preset info without bpy."""

    def test_exports_preset_names(self):
        from generators.humanoid import get_preset_names
        names = get_preset_names()
        self.assertIn("average", names)
        self.assertIn("brute", names)

    def test_exports_build_names(self):
        from generators.humanoid import get_build_names
        names = get_build_names()
        self.assertIn("lean", names)
        self.assertIn("heavy", names)

    def test_exports_skin_tone_names(self):
        from generators.humanoid import get_skin_tone_names
        names = get_skin_tone_names()
        self.assertIn("medium", names)
        self.assertIn("zombie", names)

    def test_exports_hair_style_names(self):
        from generators.humanoid import get_hair_style_names
        names = get_hair_style_names()
        self.assertIn("none", names)
        self.assertIn("spiky", names)

    def test_exports_hair_color_names(self):
        from generators.humanoid import get_hair_color_names
        names = get_hair_color_names()
        self.assertIn("black", names)
        self.assertIn("blonde", names)


if __name__ == "__main__":
    unittest.main()
