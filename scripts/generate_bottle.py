"""Top-level Blender script: generate a bottle asset.

Usage:
    blender --background --python scripts/generate_bottle.py -- [options]

Options:
    --output PATH        Output file (default: assets/bottle.glb)
    --format FORMAT      Export format: glb, gltf, fbx, obj
    --variant NAME       Bottle type: generic, whiskey, vodka, beer
    --height FLOAT       Bottle height in meters (default: 0.30)
    --theme NAME         Style theme: modern, fantasy, industrial, medieval
    --material NAME      Material override: brick, concrete, metal, wood, stone, tile
    --wear FLOAT         Wear level 0.0-1.0 (default: 0.1)
    --draco              Enable Draco mesh compression for glTF/GLB
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.bottle import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a bottle asset")
    parser.add_argument("--output", default="assets/bottle.glb")
    parser.add_argument("--format", default=None)
    parser.add_argument("--variant", default="generic",
                        choices=["generic", "whiskey", "vodka", "beer"])
    parser.add_argument("--height", type=float, default=None,
                        help="Bottle height in meters (overrides variant default)")
    parser.add_argument("--theme", default="modern")
    parser.add_argument("--material", default="metal")
    parser.add_argument("--wear", type=float, default=0.1)
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {
        "variant": args.variant,
    }
    # Only override height if explicitly supplied, so variant defaults are kept
    if args.height is not None:
        config["height"] = args.height

    style = AssetStyle(
        theme=args.theme,
        material=args.material,
        wear=args.wear,
    )

    print(f"Generating bottle: variant={args.variant}, style={style}")
    generate(config, style)

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
