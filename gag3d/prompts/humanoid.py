"""Prompt templates that coerce OpenAI Images into TRELLIS-friendly outputs.

TRELLIS.2 reconstructs whatever pose, lighting, and framing it sees in the
reference image, so for downstream rigging we constrain the generator to
produce a clean front-facing T-pose against a flat background.
"""

from __future__ import annotations

HUMANOID_TEMPLATE = """\
A single full-body 3D character concept of {description}, standing in a strict \
symmetrical T-pose with arms extended horizontally and legs together, facing \
the camera directly head-on. Front orthographic view. Feet flat on the ground. \
Neutral expression. Clean flat solid white background, no shadow, no ground \
plane, no props, no text. Even soft studio lighting. Game-ready stylized \
render, full body visible head to toe, centered in frame with margin on all \
sides. Render style: {style}.
"""


def build_humanoid_prompt(description: str, style: str = "low-poly stylized 3D, clean topology, game-asset look") -> str:
    return HUMANOID_TEMPLATE.format(description=description.strip(), style=style.strip())
