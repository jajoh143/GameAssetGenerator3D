"""Non-Blender tests for the animation system configuration."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.humanoid.animation import ANIM_PARAMS, ANIMATIONS


class TestAnimationRegistry(unittest.TestCase):
    """Test that all expected animations are registered."""

    EXPECTED = {"idle", "walk", "run", "jump", "attack"}

    def test_all_animations_registered(self):
        self.assertEqual(set(ANIMATIONS.keys()), self.EXPECTED)

    def test_all_animations_have_params(self):
        for name in self.EXPECTED:
            self.assertIn(name, ANIM_PARAMS,
                          f"Missing ANIM_PARAMS entry for '{name}'")

    def test_animations_are_callable(self):
        for name, builder in ANIMATIONS.items():
            self.assertTrue(callable(builder),
                            f"Animation '{name}' builder is not callable")


class TestAnimationParams(unittest.TestCase):
    """Validate animation parameter sanity."""

    def test_looping_animations_have_cycle_frames(self):
        for name in ("idle", "walk", "run"):
            params = ANIM_PARAMS[name]
            self.assertIn("cycle_frames", params,
                          f"{name} missing cycle_frames")
            self.assertGreater(params["cycle_frames"], 0)

    def test_oneshot_animations_have_total_frames(self):
        for name in ("jump", "attack"):
            params = ANIM_PARAMS[name]
            self.assertIn("total_frames", params,
                          f"{name} missing total_frames")
            self.assertGreater(params["total_frames"], 0)

    def test_all_have_fps(self):
        for name, params in ANIM_PARAMS.items():
            self.assertIn("fps", params, f"{name} missing fps")
            self.assertEqual(params["fps"], 24)

    def test_run_faster_than_walk(self):
        """Run cycle should complete in fewer frames than walk."""
        self.assertLess(
            ANIM_PARAMS["run"]["cycle_frames"],
            ANIM_PARAMS["walk"]["cycle_frames"],
        )

    def test_run_wider_stride_than_walk(self):
        """Run should have larger leg swing than walk."""
        self.assertGreater(
            ANIM_PARAMS["run"]["upper_leg_swing"],
            ANIM_PARAMS["walk"]["upper_leg_swing"],
        )

    def test_jump_phases_sequential(self):
        jp = ANIM_PARAMS["jump"]
        self.assertLess(jp["crouch_end"], jp["launch_end"])
        self.assertLess(jp["launch_end"], jp["apex"])
        self.assertLess(jp["apex"], jp["land_end"])
        self.assertLess(jp["land_end"], jp["total_frames"])

    def test_attack_phases_sequential(self):
        ap = ANIM_PARAMS["attack"]
        self.assertLess(ap["windup_end"], ap["strike_end"])
        self.assertLess(ap["strike_end"], ap["follow_end"])
        self.assertLess(ap["follow_end"], ap["total_frames"])


class TestHumanoidAnimationConfig(unittest.TestCase):
    """Test humanoid __init__ animation selection."""

    def test_available_animations_matches_registry(self):
        from generators.humanoid import AVAILABLE_ANIMATIONS
        self.assertEqual(set(AVAILABLE_ANIMATIONS), set(ANIMATIONS.keys()))

    def test_available_animations_is_tuple(self):
        from generators.humanoid import AVAILABLE_ANIMATIONS
        self.assertIsInstance(AVAILABLE_ANIMATIONS, tuple)


if __name__ == "__main__":
    unittest.main()
