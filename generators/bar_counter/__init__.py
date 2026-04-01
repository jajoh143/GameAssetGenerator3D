"""Bar counter generator — leather-padded bar top with footrail and back shelf."""
from generators.base import BaseAssetGenerator
from generators.style import AssetStyle

DEFAULT_CFG = {
    "width": 3.0,        # total bar length along X
    "depth": 0.7,        # bar depth along Y
    "height": 1.1,       # bar top height from floor
    "thickness": 0.05,   # counter top slab thickness
    "shelf_height": 0.9, # back shelf height
    "variation": "straight",  # "straight" | "l_shape"
}


def generate(config=None, style=None):
    """Generate a bar counter asset.

    Args:
        config: dict with dimension overrides and 'variation' key.
        style: AssetStyle instance (or None for defaults).

    Returns:
        The bar counter Blender object.
    """
    cfg = dict(DEFAULT_CFG)
    cfg.update(config or {})
    if style is None:
        style = AssetStyle(theme="industrial", material="wood", wear=0.5)
    from . import mesh
    return mesh.create_bar_counter(cfg, style)


class BarCounterGenerator(BaseAssetGenerator):
    """OOP interface for the bar counter generator."""

    DEFAULT_CFG = dict(DEFAULT_CFG)

    def _default_style(self):
        return AssetStyle(theme="industrial", material="wood", wear=0.5)

    def generate(self):
        """Generate and return the bar counter Blender object."""
        from . import mesh
        return mesh.create_bar_counter(self.cfg, self.style)
