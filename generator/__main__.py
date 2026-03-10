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


def cmd_generate(args):
    """Run a generator script in Blender's background mode."""
    blender = find_blender()
    if not blender:
        print("Error: Blender not found. Install Blender 3.6+ or set BLENDER_PATH.", file=sys.stderr)
        sys.exit(1)

    asset_type = args.asset_type
    if asset_type not in ASSET_SCRIPTS:
        print(f"Error: Unknown asset type '{asset_type}'. Available: {', '.join(ASSET_SCRIPTS)}", file=sys.stderr)
        sys.exit(1)

    script = os.path.abspath(ASSET_SCRIPTS[asset_type])
    output = os.path.abspath(args.output)

    os.makedirs(os.path.dirname(output), exist_ok=True)

    cmd = [
        blender,
        "--background",
        "--python", script,
        "--",
        "--output", output,
    ]

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
