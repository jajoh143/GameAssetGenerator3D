"""Top-level Blender script: generate an LED dance floor asset.

Usage:
    blender --background --python scripts/generate_dance_floor.py -- [options]

Options:
    --output PATH        Output file (default: assets/dance_floor.glb)
    --format FORMAT      Export format: glb, gltf, fbx, obj
    --variation NAME     Tile pattern: rainbow_grid, checkerboard, pulse_ring
    --width FLOAT        Floor width in meters (default: 6.0)
    --length FLOAT       Floor length in meters (default: 6.0)
    --tile-size FLOAT    LED tile size in meters (default: 0.5)
    --glow-strength FLOAT  Emission strength (default: 4.0)
    --theme NAME         Style theme: modern, fantasy, industrial, medieval
    --material NAME      Slab material: tile, concrete, metal, stone
    --wear FLOAT         Wear level 0.0-1.0 (default: 0.2)
    --draco              Enable Draco mesh compression for glTF/GLB
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.dance_floor import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate an LED dance floor asset")
    parser.add_argument("--output", default="assets/dance_floor.glb")
    parser.add_argument("--format", default=None)
    parser.add_argument("--variation", default="rainbow_grid",
                        choices=["rainbow_grid", "checkerboard", "pulse_ring"])
    parser.add_argument("--width", type=float, default=6.0)
    parser.add_argument("--length", type=float, default=6.0)
    parser.add_argument("--tile-size", type=float, default=0.5)
    parser.add_argument("--glow-strength", type=float, default=4.0)
    parser.add_argument("--theme", default="modern")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--wear", type=float, default=0.2)
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {
        "width": args.width,
        "length": args.length,
        "tile_size": args.tile_size,
        "glow_strength": args.glow_strength,
        "variation": args.variation,
    }

    style = AssetStyle(theme=args.theme, material=args.material, wear=args.wear)

    print(f"Generating dance floor: variation={args.variation}, style={style}")
    generate(config, style)

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
