"""Floor/ground asset generator — 6 gritty urban floor variations.

Variations:
    1. concrete    — Poured concrete slab with cracks
    2. metal_plate — Diamond-plate / industrial metal floor
    3. wood_plank  — Wooden plank flooring
    4. tile        — Cracked tile floor
    5. asphalt     — Road / parking-lot asphalt
    6. cobblestone — Brick / cobblestone paving
"""

DEFAULT_CFG = {
    "width": 4.0,
    "length": 4.0,
    "depth": 0.1,       # slab thickness
}

VARIATIONS = ("concrete", "metal_plate", "wood_plank", "tile", "asphalt", "cobblestone")


def generate(config=None, style=None):
    """Generate a floor asset.

    Args:
        config: dict with dimension overrides and 'variation' key.
        style: AssetStyle instance (or None for defaults).

    Returns:
        The floor Blender object.
    """
    from generators.style import AssetStyle

    cfg = dict(DEFAULT_CFG)
    if config:
        cfg.update(config)

    variation = cfg.pop("variation", "concrete")
    if variation not in VARIATIONS:
        raise ValueError(f"Unknown floor variation '{variation}'. Choose from: {VARIATIONS}")

    if style is None:
        mat_map = {
            "concrete": "concrete",
            "metal_plate": "metal",
            "wood_plank": "wood",
            "tile": "tile",
            "asphalt": "concrete",
            "cobblestone": "stone",
        }
        style = AssetStyle(material=mat_map[variation], wear=0.6)

    from . import mesh
    floor = mesh.create_floor(cfg, variation, style)
    return floor
