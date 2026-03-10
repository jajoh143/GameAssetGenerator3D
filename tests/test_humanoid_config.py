"""Non-Blender tests for humanoid configuration and CLI logic."""

import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCLI(unittest.TestCase):
    """Test the CLI wrapper (non-Blender parts)."""

    def test_asset_scripts_paths_exist(self):
        from generator.__main__ import ASSET_SCRIPTS
        for name, path in ASSET_SCRIPTS.items():
            resolved = os.path.abspath(path)
            self.assertTrue(
                os.path.isfile(resolved),
                f"Script for '{name}' not found at {resolved}",
            )

    def test_list_includes_humanoid(self):
        from generator.__main__ import ASSET_SCRIPTS
        self.assertIn("humanoid", ASSET_SCRIPTS)


class TestExportFormatDetection(unittest.TestCase):
    """Test export format auto-detection."""

    def test_glb_detection(self):
        from generator.export import detect_format
        self.assertEqual(detect_format("model.glb"), "glb")

    def test_fbx_detection(self):
        from generator.export import detect_format
        self.assertEqual(detect_format("model.fbx"), "fbx")

    def test_obj_detection(self):
        from generator.export import detect_format
        self.assertEqual(detect_format("model.obj"), "obj")

    def test_gltf_detection(self):
        from generator.export import detect_format
        self.assertEqual(detect_format("scene.gltf"), "gltf")

    def test_unknown_defaults_to_glb(self):
        from generator.export import detect_format
        self.assertEqual(detect_format("model.xyz"), "glb")


if __name__ == "__main__":
    unittest.main()
