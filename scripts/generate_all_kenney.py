"""Generate all four Kenney-style characters into the assets folder.

Usage:
    blender --background --python scripts/generate_all_kenney.py
"""

import sys
import os
import bpy

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.humanoid import generate
from generator.export import export

os.makedirs(os.path.join(project_root, "assets", "Characters"), exist_ok=True)


def make(name, cfg):
    # Clear scene between characters
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generate(cfg)
    out = os.path.join(project_root, "assets", "Characters", f"{name}.glb")
    export(out)
    print(f"[done] {out}")


# Character 2 — red tshirt over white longsleeve, blue jeans
make("kenney_char2", {
    "preset": "kenney",
    "hair_style": "short",
    "hair_color": "brown",
    "clothing": ["longsleeve", "tshirt", "pants"],
    "clothing_color": {"longsleeve": "white", "tshirt": "red", "pants": "navy"},
})

# Character 3 — black longsleeve, black pants, belt
make("kenney_char3", {
    "preset": "kenney",
    "hair_style": "spiky",
    "hair_color": "black",
    "clothing": ["longsleeve", "pants", "belt"],
    "clothing_color": {"longsleeve": "black", "pants": "black", "belt": "black"},
})

# Character 4 — white jacket, white pants, mustache
make("kenney_char4", {
    "preset": "kenney",
    "hair_style": "slicked",
    "hair_color": "black",
    "clothing": ["jacket", "pants"],
    "clothing_color": {"jacket": "white", "pants": "white"},
    "mustache": True,
})

print("All characters generated.")
