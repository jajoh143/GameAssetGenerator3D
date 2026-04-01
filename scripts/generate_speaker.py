"""Top-level Blender script: generate a speaker asset.

Usage:
    blender --background --python scripts/generate_speaker.py -- [options]

Options:
    --output PATH        Output file (default: assets/speaker.glb)
    --format FORMAT      Export format: glb, gltf, fbx, obj
    --variation NAME     Speaker type: floor_standing, wall_mount, subwoofer
    --width FLOAT        Cabinet width in meters (default: 0.5)
    --height FLOAT       Cabinet height in meters (default: 0.9)
    --depth FLOAT        Cabinet depth in meters (default: 0.45)
    --theme NAME         Style theme: modern, fantasy, industrial, medieval
    --material NAME      Material override: brick, concrete, metal, wood, stone, tile
    --wear FLOAT         Wear level 0.0-1.0 (default: 0.3)
    --draco              Enable Draco mesh compression for glTF/GLB
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.speaker import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a speaker asset")
    parser.add_argument("--output", default="assets/speaker.glb")
    parser.add_argument("--format", default=None)
    parser.add_argument("--variation", default="floor_standing",
                        choices=["floor_standing", "wall_mount", "subwoofer"])
    parser.add_argument("--width", type=float, default=0.5)
    parser.add_argument("--height", type=float, default=0.9)
    parser.add_argument("--depth", type=float, default=0.45)
    parser.add_argument("--theme", default="industrial")
    parser.add_argument("--material", default=None)
    parser.add_argument("--wear", type=float, default=0.3)
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {
        "width": args.width,
        "height": args.height,
        "depth": args.depth,
        "variation": args.variation,
    }

    style_kwargs = {"theme": args.theme, "wear": args.wear}
    if args.material:
        style_kwargs["material"] = args.material
    else:
        style_kwargs["material"] = "metal"

    style = AssetStyle(**style_kwargs)

    print(f"Generating speaker: variation={args.variation}, style={style}")
    generate(config, style)

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
