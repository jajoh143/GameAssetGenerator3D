"""CLI entry point: python -m generator <command> <asset_type> [options]

Wraps Blender in background mode to run the appropriate generator script.
"""

import argparse
import os
import shutil
import subprocess
import sys


BLENDER_PATH = os.environ.get("BLENDER_PATH", "blender")

ASSET_SCRIPTS = {
    "humanoid": os.path.join(
        os.path.dirname(__file__), "..", "scripts", "generate_humanoid.py"
    ),
    "wall": os.path.join(
        os.path.dirname(__file__), "..", "scripts", "generate_wall.py"
    ),
    "floor": os.path.join(
        os.path.dirname(__file__), "..", "scripts", "generate_floor.py"
    ),
}


def find_blender():
    """Locate the Blender binary."""
    path = shutil.which(BLENDER_PATH)
    if path:
        return path
    # Common install locations
    for candidate in [
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/snap/bin/blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _bpy_is_standalone():
    """Return True if the standalone bpy Python package is importable."""
    try:
        import importlib.util
        return importlib.util.find_spec("bpy") is not None
    except Exception:
        return False


def cmd_generate(args):
    """Run a generator script via Blender (or standalone bpy if Blender not found)."""
    blender = find_blender()
    if not blender and not _bpy_is_standalone():
        print(
            "Error: Blender not found and the 'bpy' package is not installed.\n"
            "  Option 1: Install Blender 3.6+ and ensure it is on PATH (or set BLENDER_PATH).\n"
            "  Option 2: pip install bpy",
            file=sys.stderr,
        )
        sys.exit(1)

    asset_type = args.asset_type
    if asset_type not in ASSET_SCRIPTS:
        print(f"Error: Unknown asset type '{asset_type}'. Available: {', '.join(ASSET_SCRIPTS)}", file=sys.stderr)
        sys.exit(1)

    script = os.path.abspath(ASSET_SCRIPTS[asset_type])
    output = os.path.abspath(args.output)

    os.makedirs(os.path.dirname(output), exist_ok=True)

    if blender:
        # Full Blender installation: run in background mode
        cmd = [blender, "--background", "--python", script, "--", "--output", output]
    else:
        # Standalone bpy package: run the script directly with the current Python
        # The generate scripts use sys.argv and split on "--", so pass it the same way
        cmd = [sys.executable, script, "--", "--output", output]

    if args.format:
        cmd.extend(["--format", args.format])
    if args.variation:
        cmd.extend(["--variation", args.variation])
    if args.theme:
        cmd.extend(["--theme", args.theme])
    if args.material:
        cmd.extend(["--material", args.material])
    if args.wear is not None:
        cmd.extend(["--wear", str(args.wear)])
    if args.animations:
        cmd.extend(["--animations", args.animations])
    if args.preset:
        cmd.extend(["--preset", args.preset])
    if args.build:
        cmd.extend(["--build", args.build])
    if args.gender:
        cmd.extend(["--gender", args.gender])
    if args.skin_tone:
        cmd.extend(["--skin-tone", args.skin_tone])
    if args.hair_style:
        cmd.extend(["--hair-style", args.hair_style])
    if args.hair_color:
        cmd.extend(["--hair-color", args.hair_color])
    if args.clothing:
        cmd.extend(["--clothing", args.clothing])
    if args.clothing_color:
        cmd.extend(["--clothing-color", args.clothing_color])
    if args.height is not None:
        cmd.extend(["--height", str(args.height)])
    if args.shoulder_width is not None:
        cmd.extend(["--shoulder-width", str(args.shoulder_width)])
    if args.hip_width is not None:
        cmd.extend(["--hip-width", str(args.hip_width)])
    if args.head_size is not None:
        cmd.extend(["--head-size", str(args.head_size)])
    if args.arm_length is not None:
        cmd.extend(["--arm-length", str(args.arm_length)])
    if args.leg_length is not None:
        cmd.extend(["--leg-length", str(args.leg_length)])
    if args.torso_length is not None:
        cmd.extend(["--torso-length", str(args.torso_length)])
    if args.limb_thickness is not None:
        cmd.extend(["--limb-thickness", str(args.limb_thickness)])
    if args.torso_depth is not None:
        cmd.extend(["--torso-depth", str(args.torso_depth)])
    if args.randomize:
        cmd.append("--randomize")
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])
    if args.draco:
        cmd.append("--draco")
    if getattr(args, "use_template", False):
        cmd.append("--use-template")
    if getattr(args, "lod", None):
        cmd.extend(["--lod", args.lod])

    print(f"Generating {asset_type} -> {output}")
    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_list(args):
    """List available asset generators."""
    print("Available asset types:")
    for name in sorted(ASSET_SCRIPTS):
        print(f"  - {name}")


def main():
    parser = argparse.ArgumentParser(
        prog="generator",
        description="GameAssetGenerator3D — procedural 3D game asset generator",
    )
    subparsers = parser.add_subparsers(dest="command")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate an asset")
    gen_parser.add_argument("asset_type", help="Type of asset to generate")
    gen_parser.add_argument("-o", "--output", default="assets/output.glb",
                            help="Output file path (default: assets/output.glb)")
    gen_parser.add_argument("-f", "--format", choices=["glb", "gltf", "fbx", "obj"],
                            help="Export format (default: inferred from extension)")
    gen_parser.add_argument("--variation", default=None,
                            help="Asset variation (e.g., brick, concrete, corrugated)")
    gen_parser.add_argument("--theme", default=None,
                            help="Style theme (modern, fantasy, industrial, medieval)")
    gen_parser.add_argument("--material", default=None,
                            help="Material type (brick, concrete, metal, wood, stone, tile)")
    gen_parser.add_argument("--wear", type=float, default=None,
                            help="Wear/damage level 0.0-1.0")
    gen_parser.add_argument("--animations", default=None,
                            help="Comma-separated animation list or 'all' "
                                 "(humanoid: idle,walk,run,jump,attack)")
    # Character variation (humanoid)
    gen_parser.add_argument("--preset", default=None,
                            help="Character preset (average, tall, short, child, brute, slender)")
    gen_parser.add_argument("--build", default=None,
                            help="Body build (lean, average, stocky, heavy)")
    gen_parser.add_argument("--gender", default=None,
                            help="Body gender (neutral, male, female)")
    gen_parser.add_argument("--skin-tone", default=None,
                            help="Skin tone name or R,G,B,A values")
    gen_parser.add_argument("--hair-style", default=None,
                            help="Hair style (none, buzzed, short, spiky, long, mohawk)")
    gen_parser.add_argument("--hair-color", default=None,
                            help="Hair color name or R,G,B,A values")
    gen_parser.add_argument("--clothing", default=None,
                            help="Clothing type or comma-separated list "
                                 "(tshirt, jacket, pants, shorts, armor, robe)")
    gen_parser.add_argument("--clothing-color", default=None,
                            help="Clothing color name or R,G,B,A values")
    gen_parser.add_argument("--height", type=float, default=None,
                            help="Character height override in meters")
    gen_parser.add_argument("--shoulder-width", type=float, default=None)
    gen_parser.add_argument("--hip-width", type=float, default=None)
    gen_parser.add_argument("--head-size", type=float, default=None)
    gen_parser.add_argument("--arm-length", type=float, default=None)
    gen_parser.add_argument("--leg-length", type=float, default=None)
    gen_parser.add_argument("--torso-length", type=float, default=None)
    gen_parser.add_argument("--limb-thickness", type=float, default=None)
    gen_parser.add_argument("--torso-depth", type=float, default=None)
    gen_parser.add_argument("--randomize", action="store_true", default=False,
                            help="Add random variation to proportions")
    gen_parser.add_argument("--seed", type=int, default=None,
                            help="Random seed for reproducible variation")
    gen_parser.add_argument("--draco", action="store_true", default=False,
                            help="Enable Draco mesh compression for glTF/GLB")
    gen_parser.add_argument("--use-template", action="store_true", default=False,
                            help="Import body from NBM .blend template instead of "
                                 "building procedurally (humanoid only)")
    gen_parser.add_argument("--lod", default=None, choices=["very_low", "low", "mid"],
                            help="Template mesh LOD tier (only with --use-template): "
                                 "very_low (<300 faces), low (300-500), mid (500+)")
    gen_parser.set_defaults(func=cmd_generate)

    # list
    list_parser = subparsers.add_parser("list", help="List available asset types")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
