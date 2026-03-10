"""Wall asset generator — 6 gritty urban wall variations.

Variations:
    1. brick      — Standard brick wall with mortar lines
    2. concrete   — Poured concrete with panel lines / cracks
    3. corrugated — Corrugated metal sheet wall
    4. plank      — Vertical wooden plank wall
    5. cinder     — Cinder block / CMU wall
    6. chainlink  — Chain-link fence (flat plane with alpha cutout)
"""

# Default wall dimensions (meters)
DEFAULT_CFG = {
    "width": 4.0,
    "height": 3.0,
    "depth": 0.2,        # wall thickness
}

VARIATIONS = ("brick", "concrete", "corrugated", "plank", "cinder", "chainlink")


def generate(config=None, style=None):
    """Generate a wall asset.

    Args:
        config: dict with dimension overrides and 'variation' key.
        style: AssetStyle instance (or None for defaults).

    Returns:
        The wall Blender object.
    """
    from generators.style import AssetStyle

    cfg = dict(DEFAULT_CFG)
    if config:
        cfg.update(config)

    variation = cfg.pop("variation", "brick")
    if variation not in VARIATIONS:
        raise ValueError(f"Unknown wall variation '{variation}'. Choose from: {VARIATIONS}")

    if style is None:
        # Map variation to a sensible default material
        mat_map = {
            "brick": "brick",
            "concrete": "concrete",
            "corrugated": "metal",
            "plank": "wood",
            "cinder": "concrete",
            "chainlink": "metal",
        }
        style = AssetStyle(material=mat_map[variation], wear=0.6)

    from . import mesh
    wall = mesh.create_wall(cfg, variation, style)
    return wall
