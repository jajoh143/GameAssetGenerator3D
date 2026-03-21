"""LED rainbow neon sign generator.

Generates a low-poly neon/LED rainbow sign asset with a dark backing panel,
emissive rainbow arc tubes (or flat bar / word strip variants), and mounting
brackets.

Variations:
    arch       — Full 7-stripe rainbow arch (default)
    flat_bars  — 7 horizontal parallel bars stacked vertically
    word       — Backing panel with a single emissive strip (text placeholder)
"""

from generators.base import BaseAssetGenerator
from generators.style import AssetStyle

DEFAULT_CFG = {
    "width": 1.4,           # total sign width
    "height": 0.5,          # total sign height
    "depth": 0.06,          # backing panel depth
    "tube_radius": 0.012,   # neon tube radius
    "tube_segments": 6,     # polygon segments on tube cross-section (low poly)
    "glow_strength": 8.0,   # emission strength
    "text": "RAINBOW",      # currently unused, reserved for future use
    "variation": "arch",    # "arch" | "word" | "flat_bars"
}

VARIATIONS = ("arch", "flat_bars", "word")


def generate(config=None, style=None):
    """Generate an LED rainbow sign asset.

    Args:
        config: dict with dimension/style overrides and optional 'variation' key.
        style: AssetStyle instance (or None for defaults).

    Returns:
        The sign Blender object.
    """
    cfg = dict(DEFAULT_CFG)
    if config:
        cfg.update(config)

    variation = cfg.get("variation", "arch")
    if variation not in VARIATIONS:
        raise ValueError(
            f"Unknown LED rainbow sign variation '{variation}'. "
            f"Choose from: {VARIATIONS}"
        )

    if style is None:
        style = AssetStyle(theme="modern", material="metal", wear=0.1)

    from . import mesh
    return mesh.create_led_rainbow_sign(cfg, style)


class LEDRainbowSignGenerator(BaseAssetGenerator):
    """OOP interface for the LED rainbow sign generator.

    Inherits shared scene utilities from BaseAssetGenerator and delegates
    mesh construction to the mesh sub-module.
    """

    DEFAULT_CFG = {
        "width": 1.4,
        "height": 0.5,
        "depth": 0.06,
        "tube_radius": 0.012,
        "tube_segments": 6,
        "glow_strength": 8.0,
        "text": "RAINBOW",
        "variation": "arch",
    }

    def _default_style(self):
        return AssetStyle(theme="modern", material="metal", wear=0.1)

    def generate(self):
        """Generate and return the LED rainbow sign Blender object."""
        from . import mesh
        return mesh.create_led_rainbow_sign(self.cfg, self.style)
