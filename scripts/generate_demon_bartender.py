"""Top-level Blender script: generate a rigged, animated demon bartender.

Usage:
    blender --background --python scripts/generate_demon_bartender.py -- [options]

Options:
    --output PATH           Output file (default: assets/demon_bartender.glb)
    --format FORMAT         Export format: glb, gltf, fbx, obj
    --animations NAMES      Comma-separated list or "all" (default: all bartender anims)
    --has-horns             Include demon horns (default: True)
    --no-horns              Disable horns
    --has-tail              Include demon tail (default: True)
    --no-tail               Disable tail
    --has-wings             Include wings (default: False)
    --horn-height FLOAT     Horn height in meters (default: 0.18)
    --theme NAME            Asset style theme: fantasy, modern, industrial, medieval
    --material NAME         Asset material: stone, brick, metal, wood, concrete, tile
    --wear FLOAT            Wear level 0.0-1.0 (default: 0.3)
    --draco                 Enable Draco mesh compression for glTF/GLB
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.demon_bartender import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a demon bartender character")

    # Output
    parser.add_argument("--output", default="assets/demon_bartender.glb",
                        help="Output file path (default: assets/demon_bartender.glb)")
    parser.add_argument("--format", default=None,
                        help="Export format: glb, gltf, fbx, obj (auto-detected from extension)")

    # Animations
    parser.add_argument("--animations", default="idle,serve_drink,wipe_bar,point",
                        help="Comma-separated animation names or 'all' "
                             "(default: idle,serve_drink,wipe_bar,point)")

    # Demon feature toggles
    parser.add_argument("--has-horns", dest="has_horns", action="store_true", default=True,
                        help="Include demon horns (default: enabled)")
    parser.add_argument("--no-horns", dest="has_horns", action="store_false",
                        help="Disable demon horns")
    parser.add_argument("--has-tail", dest="has_tail", action="store_true", default=True,
                        help="Include demon tail (default: enabled)")
    parser.add_argument("--no-tail", dest="has_tail", action="store_false",
                        help="Disable demon tail")
    parser.add_argument("--has-wings", dest="has_wings", action="store_true", default=False,
                        help="Include demon wings (default: disabled)")

    # Demon feature dimensions
    parser.add_argument("--horn-height", type=float, default=None,
                        help="Horn height in meters (default: 0.18)")

    # Style
    parser.add_argument("--theme", default="fantasy",
                        choices=["fantasy", "modern", "industrial", "medieval"],
                        help="Asset style theme (default: fantasy)")
    parser.add_argument("--material", default="stone",
                        choices=["stone", "brick", "metal", "wood", "concrete", "tile"],
                        help="Asset primary material (default: stone)")
    parser.add_argument("--wear", type=float, default=0.3,
                        help="Wear level 0.0-1.0 (default: 0.3)")

    # Export
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")

    return parser.parse_args(argv)


def main():
    args = parse_args()

    # Build style
    style = AssetStyle(theme=args.theme, material=args.material, wear=args.wear)

    # Build config dict — only include demon-specific keys; humanoid defaults
    # come from generators/demon_bartender/__init__.py DEFAULT_CFG.
    config = {
        "has_horns": args.has_horns,
        "has_tail": args.has_tail,
        "has_wings": args.has_wings,
    }

    if args.horn_height is not None:
        config["horn_height"] = args.horn_height

    # Animation selection
    if args.animations.lower() == "all":
        config["animations"] = ["idle", "serve_drink", "wipe_bar", "point"]
    else:
        config["animations"] = [a.strip() for a in args.animations.split(",") if a.strip()]

    print(
        f"Generating demon bartender: "
        f"horns={args.has_horns}, tail={args.has_tail}, wings={args.has_wings}, "
        f"theme={args.theme}/{args.material}, wear={args.wear:.2f}, "
        f"animations={config['animations']}"
    )

    armature = generate(config, style)
    print("Generation complete. Exporting...")

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
