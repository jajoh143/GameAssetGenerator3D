"""Tests for the base mesh and morph target system.

These tests verify the non-Blender aspects of the new architecture:
- Morph delta computation
- Config-to-morph mapping
- Vertex group name consistency with bone names
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generators.humanoid.morphs import compute_morph_deltas


class TestMorphDeltas(unittest.TestCase):
    """Test morph delta computation."""

    def test_identical_positions_produce_no_deltas(self):
        """Identical base and target should produce empty deltas."""
        positions = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        deltas = compute_morph_deltas(positions, positions)
        self.assertEqual(deltas, {})

    def test_single_vertex_delta(self):
        """Moving one vertex should produce a delta for that vertex only."""
        base = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        target = [(0, 0, 0), (1.5, 0, 0), (0, 1, 0)]
        deltas = compute_morph_deltas(base, target)
        self.assertEqual(len(deltas), 1)
        self.assertIn(1, deltas)
        self.assertAlmostEqual(deltas[1][0], 0.5)
        self.assertAlmostEqual(deltas[1][1], 0.0)
        self.assertAlmostEqual(deltas[1][2], 0.0)

    def test_all_vertices_move(self):
        """All vertices moving should produce deltas for all."""
        base = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        target = [(0.1, 0.1, 0.1), (1.1, 0.1, 0.1), (0.1, 1.1, 0.1)]
        deltas = compute_morph_deltas(base, target)
        self.assertEqual(len(deltas), 3)

    def test_below_threshold_ignored(self):
        """Movements smaller than threshold should be ignored."""
        base = [(0, 0, 0), (1, 0, 0)]
        target = [(1e-7, 1e-7, 1e-7), (1, 0, 0)]
        deltas = compute_morph_deltas(base, target)
        self.assertEqual(len(deltas), 0)

    def test_mismatched_lengths_raises(self):
        """Mismatched vertex counts should raise AssertionError."""
        base = [(0, 0, 0)]
        target = [(0, 0, 0), (1, 0, 0)]
        with self.assertRaises(AssertionError):
            compute_morph_deltas(base, target)

    def test_delta_is_additive(self):
        """Applying delta to base should yield target."""
        base = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        target = [(1.5, 2.3, 3.1), (4.2, 5.0, 6.8)]
        deltas = compute_morph_deltas(base, target)

        for vi, (dx, dy, dz) in deltas.items():
            result = (base[vi][0] + dx, base[vi][1] + dy, base[vi][2] + dz)
            self.assertAlmostEqual(result[0], target[vi][0], places=6)
            self.assertAlmostEqual(result[1], target[vi][1], places=6)
            self.assertAlmostEqual(result[2], target[vi][2], places=6)


class TestMorphConfig(unittest.TestCase):
    """Test morph configuration integration."""

    def test_neutral_config_detected(self):
        """Neutral average config should be detected as neutral."""
        from generators.humanoid.morphs import is_neutral_config
        from generators.humanoid.presets import PRESETS

        cfg = dict(PRESETS["average"])
        cfg["gender"] = "neutral"
        self.assertTrue(is_neutral_config(cfg))

    def test_non_neutral_config_detected(self):
        """Non-neutral configs should not be detected as neutral."""
        from generators.humanoid.morphs import is_neutral_config
        from generators.humanoid.presets import PRESETS

        cfg = dict(PRESETS["tall"])
        cfg["gender"] = "neutral"
        self.assertFalse(is_neutral_config(cfg))

    def test_gender_makes_non_neutral(self):
        """Setting gender should make config non-neutral."""
        from generators.humanoid.morphs import is_neutral_config
        from generators.humanoid.presets import PRESETS

        cfg = dict(PRESETS["average"])
        cfg["gender"] = "male"
        self.assertFalse(is_neutral_config(cfg))


class TestClothingConstants(unittest.TestCase):
    """Test clothing data constants are preserved."""

    def test_clothing_types_preserved(self):
        """All expected clothing types should be available."""
        from generators.humanoid.clothing import CLOTHING_TYPES
        expected = {"none", "short_sleeve", "long_sleeve", "v_neck", "shorts", "jeans"}
        self.assertEqual(set(CLOTHING_TYPES), expected)

    def test_clothing_colors_preserved(self):
        """All expected colors should be available."""
        from generators.humanoid.clothing import CLOTHING_COLORS
        expected_colors = {"white", "black", "grey", "red", "blue", "green",
                          "brown", "tan", "navy", "purple", "orange", "yellow",
                          "denim", "light_denim"}
        self.assertEqual(set(CLOTHING_COLORS.keys()), expected_colors)

    def test_default_colors_preserved(self):
        """Default color assignments should be preserved."""
        from generators.humanoid.clothing import CLOTHING_DEFAULT_COLORS
        self.assertEqual(CLOTHING_DEFAULT_COLORS["short_sleeve"], "red")
        self.assertEqual(CLOTHING_DEFAULT_COLORS["jeans"], "denim")
        self.assertEqual(CLOTHING_DEFAULT_COLORS["v_neck"], "navy")

    def test_color_values_are_rgba(self):
        """All color values should be 4-element tuples."""
        from generators.humanoid.clothing import CLOTHING_COLORS
        for name, color in CLOTHING_COLORS.items():
            self.assertEqual(len(color), 4, f"Color '{name}' is not RGBA")
            for c in color:
                self.assertIsInstance(c, float)


class TestBackwardCompatibility(unittest.TestCase):
    """Test that backward-compatible constants are preserved in mesh.py."""

    def test_vertex_constants_exist(self):
        """Old vertex constants should still be importable."""
        from generators.humanoid.mesh import (
            V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST,
            V_CHEST, V_NECK, V_L_SHOULDER, V_R_SHOULDER,
            V_L_ELBOW, V_R_ELBOW, V_L_ANKLE, V_R_ANKLE,
        )
        self.assertEqual(V_PELVIS, 0)
        self.assertEqual(V_NECK, 6)

    def test_region_sets_exist(self):
        """Region sets should still be importable."""
        from generators.humanoid.mesh import (
            REGION_SPINE, REGION_L_ARM, REGION_R_ARM,
            REGION_L_LEG, REGION_R_LEG,
        )
        self.assertIn(0, REGION_SPINE)  # V_PELVIS in SPINE
        self.assertIn(8, REGION_L_ARM)  # V_L_SHOULDER in L_ARM

    def test_build_body_skeleton_returns_correct_format(self):
        """Deprecated build_body_skeleton should still return (verts, edges, radii)."""
        from generators.humanoid.mesh import build_body_skeleton
        from generators.humanoid.presets import PRESETS

        cfg = dict(PRESETS["average"])
        cfg["gender"] = "neutral"
        verts, edges, radii = build_body_skeleton(cfg)

        self.assertIsInstance(verts, list)
        self.assertIsInstance(edges, list)
        self.assertIsInstance(radii, dict)
        self.assertEqual(len(verts), 33)  # 31 original + 2 inner hip
        self.assertGreater(len(edges), 0)
        self.assertGreater(len(radii), 0)


if __name__ == "__main__":
    unittest.main()
