"""Bottle asset generator — generic + 3 spirit/beer variants.

Variants:
    generic   — Standard green glass bottle
    whiskey   — Square-section amber bottle
    vodka     — Tall clear glass bottle
    beer      — Short dark brown bottle
"""

from generators.base import BaseAssetGenerator
from generators.style import AssetStyle

# ---------------------------------------------------------------------------
# Module-level default config (used by the functional generate() path)
# ---------------------------------------------------------------------------

DEFAULT_CFG = {
    "variant": "generic",
    "height": 0.30,
    "segments": 8,               # cross-section polygon vertices (low poly)
    "body_radius": 0.04,
    "body_height_ratio": 0.60,   # fraction of total height that is the body
    "shoulder_height_ratio": 0.10,
    "neck_radius": 0.016,
    "neck_height_ratio": 0.25,
    "base_chamfer": 0.005,
    "has_label": True,
    "label_height_ratio": 0.35,
    "glass_color": (0.25, 0.45, 0.25, 1.0),  # green glass
    "glass_roughness": 0.05,
    "glass_metallic": 0.0,
    "glass_alpha": 0.55,
    "label_color": (0.85, 0.82, 0.75, 1.0),
    "cap_color": (0.6, 0.6, 0.6, 1.0),
}


# ---------------------------------------------------------------------------
# Base generator class
# ---------------------------------------------------------------------------

class BottleGenerator(BaseAssetGenerator):
    """Procedural low-poly bottle generator.

    Builds a lathe-profile bottle body, an optional label band, and a cap
    using bmesh ring-sweep geometry.  Feet are at Z=0.
    """

    DEFAULT_CFG = dict(DEFAULT_CFG)

    def _default_style(self):
        return AssetStyle(theme="modern", material="metal", wear=0.1)

    def generate(self):
        """Generate and return the bottle Blender object."""
        from . import mesh
        return mesh.create_bottle(self.cfg, self.style)


# ---------------------------------------------------------------------------
# Variant subclasses — override only DEFAULT_CFG values that differ
# ---------------------------------------------------------------------------

class WhiskeyBottleGenerator(BottleGenerator):
    """Square-section amber whiskey bottle."""

    DEFAULT_CFG = {
        **BottleGenerator.DEFAULT_CFG,
        "variant": "whiskey",
        "segments": 4,
        "height": 0.28,
        "body_radius": 0.055,
        "glass_color": (0.4, 0.28, 0.1, 1.0),
        "glass_alpha": 0.6,
        "label_color": (0.7, 0.5, 0.1, 1.0),
        "cap_color": (0.3, 0.2, 0.05, 1.0),
    }


class VodkaBottleGenerator(BottleGenerator):
    """Tall clear-glass vodka bottle."""

    DEFAULT_CFG = {
        **BottleGenerator.DEFAULT_CFG,
        "variant": "vodka",
        "segments": 12,
        "height": 0.32,
        "body_radius": 0.038,
        "neck_radius": 0.014,
        "glass_color": (0.85, 0.92, 0.95, 1.0),
        "glass_alpha": 0.35,
        "label_color": (0.9, 0.9, 0.95, 1.0),
        "cap_color": (0.85, 0.85, 0.9, 1.0),
    }


class BeerBottleGenerator(BottleGenerator):
    """Short dark-brown beer bottle."""

    DEFAULT_CFG = {
        **BottleGenerator.DEFAULT_CFG,
        "variant": "beer",
        "segments": 8,
        "height": 0.24,
        "body_radius": 0.036,
        "body_height_ratio": 0.55,
        "neck_radius": 0.012,
        "glass_color": (0.25, 0.12, 0.03, 1.0),
        "glass_alpha": 0.7,
        "label_color": (0.9, 0.75, 0.2, 1.0),
        "cap_color": (0.35, 0.35, 0.4, 1.0),
    }


# ---------------------------------------------------------------------------
# Variant dispatch map + module-level generate()
# ---------------------------------------------------------------------------

VARIANTS = {
    "generic": BottleGenerator,
    "whiskey": WhiskeyBottleGenerator,
    "vodka": VodkaBottleGenerator,
    "beer": BeerBottleGenerator,
}


def generate(config=None, style=None):
    """Generate a bottle asset.

    Args:
        config: dict with parameter overrides and optional 'variant' key.
                Variant choices: generic, whiskey, vodka, beer.
        style:  AssetStyle instance (or None for defaults).

    Returns:
        The bottle Blender object.
    """
    cfg = config or {}
    variant = cfg.get("variant", "generic")
    cls = VARIANTS.get(variant, BottleGenerator)
    return cls(config=cfg, style=style).generate()
