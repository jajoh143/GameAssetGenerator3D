"""Top-level Blender script: generate a rigged, animated low-poly humanoid.

Usage:
    blender --background --python scripts/generate_humanoid.py -- [options]

Options:
    --output PATH         Output file (default: assets/humanoid.glb)
    --format FORMAT       Export format: glb, gltf, fbx, obj
    --preset NAME         Character preset: average, tall, short, child, brute, slender
    --build NAME          Body build: lean, average, stocky, heavy
    --skin-tone NAME      Skin tone name or R,G,B,A values
    --height FLOAT        Override height in meters
    --animations NAMES    Comma-separated animation list or "all"
    --randomize           Add slight random variation to proportions
    --seed INT            Random seed for reproducible variation
"""

import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generators.humanoid import generate
from generator.export import export


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Generate a low-poly humanoid")
    parser.add_argument("--output", default="assets/humanoid.glb")
    parser.add_argument("--format", default=None)

    # Character variation
    parser.add_argument("--preset", default="average",
                        help="Character archetype (average, tall, short, child, brute, slender)")
    parser.add_argument("--build", default="average",
                        help="Body build (lean, average, stocky, heavy)")
    parser.add_argument("--skin-tone", default="medium",
                        help="Skin tone name or R,G,B,A (e.g., 'tan' or '0.5,0.4,0.3,1.0')")

    # Direct proportion overrides
    parser.add_argument("--height", type=float, default=None)
    parser.add_argument("--shoulder-width", type=float, default=None)
    parser.add_argument("--hip-width", type=float, default=None)
    parser.add_argument("--head-size", type=float, default=None)
    parser.add_argument("--arm-length", type=float, default=None)
    parser.add_argument("--leg-length", type=float, default=None)
    parser.add_argument("--torso-length", type=float, default=None)
    parser.add_argument("--limb-thickness", type=float, default=None)
    parser.add_argument("--torso-depth", type=float, default=None)

    # Variation
    parser.add_argument("--randomize", action="store_true",
                        help="Add slight random variation for crowd diversity")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible variation")

    # Animations
    parser.add_argument("--animations", default="all",
                        help="Comma-separated list or 'all'")

    return parser.parse_args(argv)


def _parse_skin_tone(value):
    """Parse skin tone — either a name or comma-separated RGBA."""
    if "," in value:
        parts = [float(x.strip()) for x in value.split(",")]
        if len(parts) == 3:
            parts.append(1.0)
        return tuple(parts)
    return value


def main():
    args = parse_args()

    # Build config dict
    config = {
        "preset": args.preset,
        "build": args.build,
        "skin_tone": _parse_skin_tone(args.skin_tone),
        "randomize": args.randomize,
    }

    if args.seed is not None:
        config["seed"] = args.seed

    # Animation selection
    if args.animations == "all":
        config["animations"] = "all"
    else:
        config["animations"] = [a.strip() for a in args.animations.split(",")]

    # Direct proportion overrides (only include if explicitly set)
    override_map = {
        "height": args.height,
        "shoulder_width": args.shoulder_width,
        "hip_width": args.hip_width,
        "head_size": args.head_size,
        "arm_length": args.arm_length,
        "leg_length": args.leg_length,
        "torso_length": args.torso_length,
        "limb_thickness": args.limb_thickness,
        "torso_depth": args.torso_depth,
    }
    for key, val in override_map.items():
        if val is not None:
            config[key] = val

    print(f"Generating humanoid: preset={args.preset}, build={args.build}, "
          f"skin={args.skin_tone}")
    armature = generate(config)
    print("Generation complete. Exporting...")

    output = os.path.abspath(args.output)
    export(output, args.format)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
