"""Club speaker generator — PA/DJ speaker cabinet with tweeter and woofer.

Variations:
    1. floor_standing  — Full PA/DJ speaker with woofer + tweeter + carry handle
    2. wall_mount      — Compact speaker with wall bracket, no handle
    3. subwoofer       — Wide/short cabinet with one large woofer, no tweeter/handle
"""

from generators.base import BaseAssetGenerator
from generators.style import AssetStyle

DEFAULT_CFG = {
    "width": 0.5,
    "height": 0.9,
    "depth": 0.45,
    "woofer_radius": 0.18,
    "tweeter_radius": 0.04,
    "corner_radius": 0.02,
    "variation": "floor_standing",   # "floor_standing" | "wall_mount" | "subwoofer"
}

VARIATIONS = ("floor_standing", "wall_mount", "subwoofer")


def generate(config=None, style=None):
    """Generate a speaker asset.

    Args:
        config: dict with dimension overrides and 'variation' key.
        style: AssetStyle instance (or None for defaults).

    Returns:
        The speaker Blender object.
    """
    cfg = dict(DEFAULT_CFG)
    if config:
        cfg.update(config)

    variation = cfg.get("variation", "floor_standing")
    if variation not in VARIATIONS:
        raise ValueError(
            f"Unknown speaker variation '{variation}'. Choose from: {VARIATIONS}"
        )

    if style is None:
        style = AssetStyle(theme="industrial", material="metal", wear=0.3)

    from . import mesh
    return mesh.create_speaker(cfg, style)


class SpeakerGenerator(BaseAssetGenerator):
    """OOP interface for the floor-standing PA/DJ speaker generator."""

    DEFAULT_CFG = {
        "width": 0.5,
        "height": 0.9,
        "depth": 0.45,
        "woofer_radius": 0.18,
        "tweeter_radius": 0.04,
        "corner_radius": 0.02,
        "variation": "floor_standing",
    }

    def _default_style(self):
        return AssetStyle(theme="industrial", material="metal", wear=0.3)

    def generate(self):
        """Generate and return the speaker Blender object."""
        from . import mesh
        return mesh.create_speaker(self.cfg, self.style)


class SubwooferGenerator(SpeakerGenerator):
    """OOP interface for the subwoofer speaker generator.

    Wider, shorter cabinet with a single large woofer cone.
    """

    DEFAULT_CFG = {
        "width": 0.6,
        "height": 0.6,
        "depth": 0.55,
        "woofer_radius": 0.25,
        "tweeter_radius": 0.04,
        "corner_radius": 0.02,
        "variation": "subwoofer",
    }


class WallMountSpeakerGenerator(SpeakerGenerator):
    """OOP interface for the wall-mount speaker generator.

    Compact cabinet with mounting bracket, no handle.
    """

    DEFAULT_CFG = {
        "width": 0.3,
        "height": 0.5,
        "depth": 0.25,
        "woofer_radius": 0.10,
        "tweeter_radius": 0.03,
        "corner_radius": 0.02,
        "variation": "wall_mount",
    }
