"""Top-level Blender script: generate a rigged, animated low-poly humanoid.

Usage:
    blender --background --python scripts/generate_humanoid.py -- [options]

Options:
    --output PATH    Output file (default: assets/humanoid.glb)
    --format FORMAT  Export format: glb, gltf, fbx, obj (default: from extension)
    --height FLOAT   Character height in meters (default: 1.8)
"""

import sys
import os
import argparse

# Add project root to path so we can import our modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.humanoid import generate
from generator.export import export


def parse_args():
    """Parse arguments after the '--' separator."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a low-poly humanoid")
    parser.add_argument("--output", default="assets/humanoid.glb",
                        help="Output file path")
    parser.add_argument("--format", default=None,
                        help="Export format (glb, gltf, fbx, obj)")
    parser.add_argument("--height", type=float, default=1.8,
                        help="Character height in meters")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    config = {"height": args.height}

    print(f"Generating humanoid (height={args.height}m)...")
    armature = generate(config)
    print("Generation complete. Exporting...")

    output = os.path.abspath(args.output)
    export(output, args.format)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
