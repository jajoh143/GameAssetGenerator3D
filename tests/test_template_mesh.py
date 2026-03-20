"""Non-Blender tests for the template mesh pipeline.

These tests validate path resolution, config propagation, and error handling
without requiring Blender or importing bpy.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.humanoid.template_mesh import (
    _resolve_blend_path,
    VALID_LODS,
    _TEMPLATE_DIR,
)
from generators.humanoid.presets import resolve_config


TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "TemplateMeshes")
)


class TestResolveBendPath(unittest.TestCase):

    def test_valid_combinations_exist_on_disk(self):
        """Every gender/lod combination should resolve to a real file."""
        for lod in VALID_LODS:
            for gender in ("neutral", "male", "female"):
                path = _resolve_blend_path(gender, lod)
                self.assertTrue(
                    os.path.isfile(path),
                    f"Expected template blend at: {path}",
                )

    def test_neutral_maps_to_male(self):
        """'neutral' gender should use the Male .blend file."""
        path = _resolve_blend_path("neutral", "low")
        self.assertIn("Male", os.path.basename(path))

    def test_female_maps_to_female(self):
        path = _resolve_blend_path("female", "low")
        self.assertIn("Female", os.path.basename(path))

    def test_very_low_lod(self):
        path = _resolve_blend_path("male", "very_low")
        self.assertIn("VeryLowpoly", os.path.basename(path))

    def test_low_lod(self):
        path = _resolve_blend_path("male", "low")
        self.assertIn("Lowpoly", os.path.basename(path))
        self.assertNotIn("VeryLowpoly", os.path.basename(path))
        self.assertNotIn("Midpoly", os.path.basename(path))

    def test_mid_lod(self):
        path = _resolve_blend_path("female", "mid")
        self.assertIn("Midpoly", os.path.basename(path))

    def test_invalid_lod_raises(self):
        with self.assertRaises(ValueError):
            _resolve_blend_path("male", "ultra")

    def test_all_six_files_are_distinct(self):
        """Each gender/lod combo should point to a different file."""
        paths = set()
        for lod in VALID_LODS:
            for gender in ("male", "female"):
                paths.add(_resolve_blend_path(gender, lod))
        self.assertEqual(len(paths), 6)


class TestResolveConfigTemplatePropagation(unittest.TestCase):
    """Check that use_template and lod survive resolve_config unchanged."""

    def test_use_template_false_by_default(self):
        cfg = resolve_config()
        self.assertFalse(cfg["use_template"])

    def test_use_template_true_propagates(self):
        cfg = resolve_config(use_template=True, lod="mid")
        self.assertTrue(cfg["use_template"])
        self.assertEqual(cfg["lod"], "mid")

    def test_lod_default_is_low(self):
        cfg = resolve_config(use_template=True)
        self.assertEqual(cfg["lod"], "low")

    def test_overrides_can_set_use_template(self):
        cfg = resolve_config(overrides={"use_template": True, "lod": "very_low"})
        self.assertTrue(cfg["use_template"])
        self.assertEqual(cfg["lod"], "very_low")

    def test_all_lods_accepted(self):
        for lod in VALID_LODS:
            cfg = resolve_config(use_template=True, lod=lod)
            self.assertEqual(cfg["lod"], lod)


class TestTemplateFileSizes(unittest.TestCase):
    """Sanity-check that the .blend files are non-trivially sized."""

    def test_all_blends_above_100kb(self):
        for fname in os.listdir(TEMPLATE_DIR):
            if fname.endswith(".blend"):
                full = os.path.join(TEMPLATE_DIR, fname)
                size = os.path.getsize(full)
                self.assertGreater(
                    size, 100_000,
                    f"{fname} is suspiciously small ({size} bytes) — may be corrupt",
                )

    def test_midpoly_larger_than_lowpoly(self):
        """Midpoly files should be bigger than their lowpoly counterparts."""
        for sex in ("Male", "Female"):
            mid = os.path.getsize(
                os.path.join(TEMPLATE_DIR, f"NBM_Midpoly_{sex}.blend")
            )
            low = os.path.getsize(
                os.path.join(TEMPLATE_DIR, f"NBM_Lowpoly_{sex}.blend")
            )
            self.assertGreater(
                mid, low,
                f"Midpoly {sex} ({mid}B) should be larger than Lowpoly {sex} ({low}B)",
            )


if __name__ == "__main__":
    unittest.main()
