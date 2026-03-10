"""Shared asset style configuration.

Provides a structured way to parameterize the visual style of generated
assets. Every environment/prop generator accepts an AssetStyle to control
material type, theme, wear level, and color palette.

Usage:
    style = AssetStyle(theme="modern", material="concrete", wear=0.7)
    create_wall(cfg, style)
"""


# Valid values for each style axis
THEMES = ("modern", "fantasy", "industrial", "medieval")
MATERIALS = ("brick", "concrete", "metal", "wood", "stone", "tile")
WEAR_RANGE = (0.0, 1.0)  # 0 = pristine, 1 = heavily worn

# Material color palettes: (base_color_rgba, roughness, metallic)
# Each material has a "clean" and "worn" variant; actual color is
# interpolated based on wear level.
MATERIAL_PROPERTIES = {
    "brick": {
        "clean": ((0.55, 0.22, 0.12, 1.0), 0.85, 0.0),
        "worn":  ((0.35, 0.18, 0.12, 1.0), 0.95, 0.0),
    },
    "concrete": {
        "clean": ((0.62, 0.60, 0.57, 1.0), 0.90, 0.0),
        "worn":  ((0.40, 0.38, 0.36, 1.0), 0.95, 0.0),
    },
    "metal": {
        "clean": ((0.58, 0.58, 0.60, 1.0), 0.35, 0.85),
        "worn":  ((0.38, 0.34, 0.30, 1.0), 0.70, 0.50),
    },
    "wood": {
        "clean": ((0.45, 0.30, 0.15, 1.0), 0.80, 0.0),
        "worn":  ((0.30, 0.22, 0.12, 1.0), 0.92, 0.0),
    },
    "stone": {
        "clean": ((0.50, 0.48, 0.45, 1.0), 0.90, 0.0),
        "worn":  ((0.35, 0.33, 0.30, 1.0), 0.95, 0.0),
    },
    "tile": {
        "clean": ((0.70, 0.68, 0.65, 1.0), 0.40, 0.1),
        "worn":  ((0.45, 0.42, 0.38, 1.0), 0.75, 0.05),
    },
}

# Theme-specific color tint multipliers (RGB) to shift palette
THEME_TINTS = {
    "modern":     (1.0, 1.0, 1.05),    # slight cool/blue tint
    "fantasy":    (1.05, 0.95, 1.1),    # purple-ish tint
    "industrial": (0.9, 0.88, 0.85),    # desaturated warm
    "medieval":   (1.0, 0.95, 0.85),    # warm/yellowish
}


class AssetStyle:
    """Parameterizes the visual style of a generated asset.

    Attributes:
        theme: Overall aesthetic ('modern', 'fantasy', 'industrial', 'medieval').
        material: Primary surface material.
        wear: Wear/damage level from 0.0 (pristine) to 1.0 (heavily worn).
    """

    def __init__(self, theme="modern", material="concrete", wear=0.5):
        if theme not in THEMES:
            raise ValueError(f"Unknown theme '{theme}'. Choose from: {THEMES}")
        if material not in MATERIALS:
            raise ValueError(f"Unknown material '{material}'. Choose from: {MATERIALS}")
        wear = max(WEAR_RANGE[0], min(WEAR_RANGE[1], float(wear)))

        self.theme = theme
        self.material = material
        self.wear = wear

    def get_color(self):
        """Return the interpolated RGBA base color for this style."""
        props = MATERIAL_PROPERTIES[self.material]
        clean_c = props["clean"][0]
        worn_c = props["worn"][0]
        tint = THEME_TINTS[self.theme]
        w = self.wear

        color = tuple(
            min(1.0, ((1 - w) * clean_c[i] + w * worn_c[i]) * (tint[i] if i < 3 else 1.0))
            for i in range(4)
        )
        return color

    def get_roughness(self):
        """Return interpolated roughness."""
        props = MATERIAL_PROPERTIES[self.material]
        return (1 - self.wear) * props["clean"][1] + self.wear * props["worn"][1]

    def get_metallic(self):
        """Return interpolated metallic value."""
        props = MATERIAL_PROPERTIES[self.material]
        return (1 - self.wear) * props["clean"][2] + self.wear * props["worn"][2]

    def to_dict(self):
        """Serialize to a plain dict (for CLI passthrough)."""
        return {"theme": self.theme, "material": self.material, "wear": self.wear}

    @classmethod
    def from_dict(cls, d):
        """Create from a dict."""
        return cls(
            theme=d.get("theme", "modern"),
            material=d.get("material", "concrete"),
            wear=d.get("wear", 0.5),
        )

    def __repr__(self):
        return f"AssetStyle(theme={self.theme!r}, material={self.material!r}, wear={self.wear})"
