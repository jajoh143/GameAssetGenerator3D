"""Top-level Blender script: generate a wall asset.

Usage:
    blender --background --python scripts/generate_wall.py -- [options]

Options:
    --output PATH        Output file (default: assets/wall.glb)
    --format FORMAT      Export format: glb, gltf, fbx, obj
    --variation NAME     Wall type: brick, concrete, corrugated, plank, cinder, chainlink
    --width FLOAT        Wall width in meters (default: 4.0)
    --height FLOAT       Wall height in meters (default: 3.0)
    --theme NAME         Style theme: modern, fantasy, industrial, medieval
    --material NAME      Material override: brick, concrete, metal, wood, stone, tile
    --wear FLOAT         Wear level 0.0-1.0 (default: 0.6)
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.wall import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a wall asset")
    parser.add_argument("--output", default="assets/wall.glb")
    parser.add_argument("--format", default=None)
    parser.add_argument("--variation", default="brick")
    parser.add_argument("--width", type=float, default=4.0)
    parser.add_argument("--height", type=float, default=3.0)
    parser.add_argument("--theme", default="modern")
    parser.add_argument("--material", default=None)
    parser.add_argument("--wear", type=float, default=0.6)
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {
        "width": args.width,
        "height": args.height,
        "depth": 0.2,
        "variation": args.variation,
    }

    style_kwargs = {"theme": args.theme, "wear": args.wear}
    if args.material:
        style_kwargs["material"] = args.material
    else:
        mat_map = {
            "brick": "brick", "concrete": "concrete", "corrugated": "metal",
            "plank": "wood", "cinder": "concrete", "chainlink": "metal",
        }
        style_kwargs["material"] = mat_map.get(args.variation, "concrete")

    style = AssetStyle(**style_kwargs)

    print(f"Generating wall: variation={args.variation}, style={style}")
    generate(config, style)

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
