"""Top-level Blender script: generate an LED rainbow neon sign asset.

Usage:
    blender --background --python scripts/generate_led_rainbow_sign.py -- [options]

Options:
    --output PATH          Output file (default: assets/led_rainbow_sign.glb)
    --format FORMAT        Export format: glb, gltf, fbx, obj
    --variation NAME       Sign type: arch, flat_bars, word  (default: arch)
    --width FLOAT          Sign width in meters  (default: 1.4)
    --height FLOAT         Sign height in meters (default: 0.5)
    --glow-strength FLOAT  Emission strength for neon tubes (default: 8.0)
    --theme NAME           Style theme: modern, fantasy, industrial, medieval
    --material NAME        Material override: brick, concrete, metal, wood, stone, tile
    --wear FLOAT           Wear level 0.0-1.0 (default: 0.1)
    --draco                Enable Draco mesh compression for glTF/GLB
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.led_rainbow_sign import generate
from generators.style import AssetStyle
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate an LED rainbow neon sign asset")
    parser.add_argument("--output", default="assets/led_rainbow_sign.glb")
    parser.add_argument("--format", default=None)
    parser.add_argument("--variation", default="arch",
                        choices=["arch", "flat_bars", "word"],
                        help="Sign variation: arch (default), flat_bars, word")
    parser.add_argument("--width", type=float, default=1.4,
                        help="Sign width in meters (default: 1.4)")
    parser.add_argument("--height", type=float, default=0.5,
                        help="Sign height in meters (default: 0.5)")
    parser.add_argument("--glow-strength", type=float, default=8.0,
                        dest="glow_strength",
                        help="Emission strength for neon tubes (default: 8.0)")
    parser.add_argument("--theme", default="modern",
                        choices=["modern", "fantasy", "industrial", "medieval"])
    parser.add_argument("--material", default="metal",
                        help="Backing panel material override")
    parser.add_argument("--wear", type=float, default=0.1,
                        help="Wear level 0.0-1.0 (default: 0.1)")
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {
        "width": args.width,
        "height": args.height,
        "depth": 0.06,
        "glow_strength": args.glow_strength,
        "variation": args.variation,
    }

    style = AssetStyle(
        theme=args.theme,
        material=args.material,
        wear=args.wear,
    )

    print(
        f"Generating LED rainbow sign: variation={args.variation}, "
        f"width={args.width}, height={args.height}, "
        f"glow_strength={args.glow_strength}, style={style}"
    )
    generate(config, style)

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
