"""Prop prompt template — single object, three-quarter view, flat background."""

from __future__ import annotations

PROP_TEMPLATE = """\
A single 3D game prop of {description}, isolated against a clean flat solid \
white background, three-quarter front view, centered with margin on all \
sides, no shadow, no ground plane, no text, no scale reference. Even soft \
studio lighting. Render style: {style}.
"""


def build_prop_prompt(description: str, style: str = "stylized 3D game asset, PBR materials") -> str:
    return PROP_TEMPLATE.format(description=description.strip(), style=style.strip())
