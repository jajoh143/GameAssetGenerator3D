"""Demon bartender generator — extends humanoid with demon features and bartender animations."""

from generators.base import BaseAssetGenerator
from generators.style import AssetStyle

# Humanoid config keys that get passed through to the humanoid generator
HUMANOID_KEYS = {
    "height", "shoulder_width", "hip_width", "head_size",
    "arm_length", "leg_length", "torso_length", "neck_length",
    "hand_size", "foot_length", "foot_width", "limb_thickness",
    "torso_depth", "gender", "skin_tone",
}

DEFAULT_CFG = {
    # Humanoid base proportions (brute/large build for intimidating demon)
    "height": 1.90,
    "shoulder_width": 0.32,
    "hip_width": 0.14,
    "head_size": 0.23,
    "arm_length": 0.68,
    "leg_length": 0.52,
    "torso_length": 0.52,
    "neck_length": 0.07,
    "hand_size": 0.08,
    "foot_length": 0.22,
    "foot_width": 0.09,
    "limb_thickness": 1.2,
    "torso_depth": 0.22,
    "gender": "neutral",
    "skin_tone": (0.15, 0.02, 0.02, 1.0),  # dark crimson demon skin
    # Demon-specific
    "has_horns": True,
    "horn_height": 0.18,
    "horn_curve": 0.08,     # how much horns curve outward
    "has_tail": True,
    "tail_length": 0.55,
    "has_wings": False,
    "eye_color": (1.0, 0.1, 0.0, 1.0),  # glowing red eyes
    # Animations to include
    "animations": ["idle", "serve_drink", "wipe_bar", "point"],
}


def generate(config=None, style=None):
    cfg = dict(DEFAULT_CFG)
    cfg.update(config or {})
    if style is None:
        style = AssetStyle(theme="fantasy", material="stone", wear=0.3)
    from . import mesh, animation
    return DemonBartenderGenerator(config=cfg, style=style).generate()


class DemonBartenderGenerator(BaseAssetGenerator):
    DEFAULT_CFG = DEFAULT_CFG  # reference module-level dict

    def _default_style(self):
        return AssetStyle(theme="fantasy", material="stone", wear=0.3)

    def generate(self):
        from . import mesh, animation as anim_module
        import bpy

        # 1. Generate humanoid base
        humanoid_cfg = {k: v for k, v in self.cfg.items() if k in HUMANOID_KEYS}
        from generators.humanoid import generate as humanoid_generate
        armature = humanoid_generate(humanoid_cfg, self.style)

        # 2. Find the body mesh (first mesh child of armature)
        body_obj = None
        for child in armature.children:
            if child.type == 'MESH':
                body_obj = child
                break

        # 3. Add demon features
        if self.cfg.get("has_horns"):
            mesh.add_horns(armature, self.cfg)
        if self.cfg.get("has_tail"):
            mesh.add_tail(armature, self.cfg)

        # 4. Add bartender animations
        anims = self.cfg.get("animations", ["idle", "serve_drink"])
        anim_module.create_bartender_animations(armature, anims)

        return armature
