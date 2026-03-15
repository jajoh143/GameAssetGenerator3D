#!/usr/bin/env python3
"""Interactive console prompt for generating 3D game assets.

Run with:
    python3 generate.py

Walks you through asset type selection and all available options,
then invokes the generator via `python -m generator generate ...`.
"""

import os
import sys
import subprocess


# ─── Asset registry ───────────────────────────────────────────────────────────

ASSETS = {
    "humanoid": {
        "description": "Low-poly rigged humanoid character with animations",
        "default_output": "assets/humanoid.glb",
    },
    "wall": {
        "description": "Modular wall segment with material and wear",
        "default_output": "assets/wall.glb",
    },
    "floor": {
        "description": "Modular floor tile with material and wear",
        "default_output": "assets/floor.glb",
    },
}

# ─── Humanoid options ─────────────────────────────────────────────────────────

HUMANOID_PRESETS = ["average", "tall", "short", "child", "brute", "slender"]
HUMANOID_BUILDS = ["lean", "average", "stocky", "heavy"]
HUMANOID_SKIN_TONES = [
    "light", "fair", "medium", "olive", "tan", "brown", "dark",
    "zombie", "orc", "frost", "ember", "shadow",
]
HUMANOID_HAIR_STYLES = ["none", "buzzed", "short", "spiky", "long", "mohawk"]
HUMANOID_HAIR_COLORS = [
    "black", "dark_brown", "brown", "auburn", "red", "blonde",
    "platinum", "white", "grey", "blue", "green", "purple", "pink",
]
HUMANOID_ANIMATIONS = ["idle", "walk", "run", "jump", "attack"]
HUMANOID_CLOTHING_TYPES = ["none", "tshirt", "jacket", "pants", "shorts", "armor", "robe"]
HUMANOID_CLOTHING_COLORS = [
    "white", "black", "grey", "red", "blue", "green", "brown",
    "tan", "navy", "purple", "orange", "yellow",
    "steel", "gold", "bronze",
]

# ─── Wall / Floor options ─────────────────────────────────────────────────────

WALL_VARIATIONS = ["brick", "concrete", "corrugated", "plank", "cinder", "chainlink"]
FLOOR_VARIATIONS = ["concrete", "metal_plate", "wood_plank", "tile", "asphalt", "cobblestone"]
THEMES = ["modern", "fantasy", "industrial", "medieval"]
MATERIALS = ["brick", "concrete", "metal", "wood", "stone", "tile"]
EXPORT_FORMATS = ["glb", "gltf", "fbx", "obj"]


# ─── Prompt helpers ───────────────────────────────────────────────────────────

def prompt_choice(label, options, default=None, allow_skip=True):
    """Show a numbered list and return the chosen value."""
    print(f"\n  {label}")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else ""
        print(f"    {i}) {opt}{marker}")
    if allow_skip:
        print(f"    Enter) {'Keep default: ' + str(default) if default else 'Skip'}")

    while True:
        raw = input("  > ").strip()
        if raw == "" and (default is not None or allow_skip):
            return default
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            # Allow typing the option name directly
            if raw in options:
                return raw
        print(f"    Please enter 1-{len(options)} or press Enter for default.")


def prompt_multi(label, options, default_all=True):
    """Let the user pick multiple items from a list. Returns a list."""
    print(f"\n  {label}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    if default_all:
        print(f"    Enter) All")
    else:
        print(f"    Enter) None")

    print("    Separate choices with commas, e.g.: 1,3,5")

    while True:
        raw = input("  > ").strip()
        if raw == "":
            return list(options) if default_all else []
        if raw.lower() == "all":
            return list(options)
        if raw.lower() == "none":
            return []
        try:
            indices = [int(x.strip()) for x in raw.split(",")]
            if all(1 <= i <= len(options) for i in indices):
                return [options[i - 1] for i in indices]
        except ValueError:
            pass
        print(f"    Please enter comma-separated numbers (1-{len(options)}), 'all', or 'none'.")


def prompt_float(label, default=None, min_val=None, max_val=None):
    """Prompt for an optional float value."""
    suffix = f" (default: {default})" if default is not None else " (Enter to skip)"
    print(f"\n  {label}{suffix}")

    while True:
        raw = input("  > ").strip()
        if raw == "":
            return default
        try:
            val = float(raw)
            if min_val is not None and val < min_val:
                print(f"    Must be >= {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"    Must be <= {max_val}")
                continue
            return val
        except ValueError:
            print("    Please enter a number.")


def prompt_yes_no(label, default=False):
    """Prompt for a yes/no answer."""
    hint = "[y/N]" if not default else "[Y/n]"
    print(f"\n  {label} {hint}")
    raw = input("  > ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


def prompt_string(label, default=None):
    """Prompt for a string value."""
    suffix = f" (default: {default})" if default else ""
    print(f"\n  {label}{suffix}")
    raw = input("  > ").strip()
    return raw if raw else default


# ─── Asset-specific prompts ───────────────────────────────────────────────────

def prompt_humanoid():
    """Gather all humanoid options and return CLI args list."""
    args = []

    print("\n── Character Preset ──")
    preset = prompt_choice("Body type:", HUMANOID_PRESETS, default="average")
    args.extend(["--preset", preset])

    build = prompt_choice("Build:", HUMANOID_BUILDS, default="average")
    args.extend(["--build", build])

    print("\n── Appearance ──")
    skin = prompt_choice("Skin tone:", HUMANOID_SKIN_TONES, default="medium")
    args.extend(["--skin-tone", skin])

    hair_style = prompt_choice("Hair style:", HUMANOID_HAIR_STYLES, default="short")
    args.extend(["--hair-style", hair_style])

    if hair_style != "none":
        hair_color = prompt_choice("Hair color:", HUMANOID_HAIR_COLORS, default="brown")
        args.extend(["--hair-color", hair_color])

    print("\n── Clothing ──")
    clothing = prompt_multi("What clothing? (pick multiple for combos, e.g. tshirt + pants):",
                            HUMANOID_CLOTHING_TYPES[1:],  # exclude "none"
                            default_all=False)
    if not clothing:
        # Default outfit: tshirt + pants
        clothing = ["tshirt", "pants"]
        print("    Using default: tshirt + pants")
    args.extend(["--clothing", ",".join(clothing)])

    if prompt_yes_no("Override clothing color? (default: grey shirt, navy pants)", default=False):
        clothing_color = prompt_choice("Clothing color (all pieces):", HUMANOID_CLOTHING_COLORS, default="grey")
        args.extend(["--clothing-color", clothing_color])

    print("\n── Animations ──")
    anims = prompt_multi("Which animations to include?", HUMANOID_ANIMATIONS, default_all=True)
    if len(anims) == len(HUMANOID_ANIMATIONS):
        args.extend(["--animations", "all"])
    elif anims:
        args.extend(["--animations", ",".join(anims)])
    else:
        args.extend(["--animations", "idle"])  # at least idle

    print("\n── Proportion Overrides (optional) ──")
    if prompt_yes_no("Customize body proportions?", default=False):
        height = prompt_float("Height (meters):", default=None, min_val=0.5, max_val=3.0)
        if height is not None:
            args.extend(["--height", str(height)])

        shoulder_w = prompt_float("Shoulder width:", default=None, min_val=0.1, max_val=1.0)
        if shoulder_w is not None:
            args.extend(["--shoulder-width", str(shoulder_w)])

        hip_w = prompt_float("Hip width:", default=None, min_val=0.1, max_val=1.0)
        if hip_w is not None:
            args.extend(["--hip-width", str(hip_w)])

        head_size = prompt_float("Head size:", default=None, min_val=0.1, max_val=0.5)
        if head_size is not None:
            args.extend(["--head-size", str(head_size)])

        torso_len = prompt_float("Torso length:", default=None, min_val=0.2, max_val=1.0)
        if torso_len is not None:
            args.extend(["--torso-length", str(torso_len)])

        limb_thick = prompt_float("Limb thickness (multiplier):", default=None, min_val=0.3, max_val=2.0)
        if limb_thick is not None:
            args.extend(["--limb-thickness", str(limb_thick)])

    if prompt_yes_no("Add random variation (for crowd diversity)?", default=False):
        args.append("--randomize")
        seed = prompt_float("Random seed (Enter for random):", default=None)
        if seed is not None:
            args.extend(["--seed", str(int(seed))])

    return args


def prompt_wall():
    """Gather wall options and return CLI args list."""
    args = []

    variation = prompt_choice("Wall type:", WALL_VARIATIONS, default="brick")
    args.extend(["--variation", variation])

    theme = prompt_choice("Theme:", THEMES, default="modern")
    args.extend(["--theme", theme])

    material = prompt_choice("Material override:", MATERIALS, default=None)
    if material:
        args.extend(["--material", material])

    width = prompt_float("Width (meters):", default=4.0, min_val=0.5, max_val=20.0)
    args.extend(["--width", str(width)])

    height = prompt_float("Height (meters):", default=3.0, min_val=0.5, max_val=20.0)
    args.extend(["--height", str(height)])

    wear = prompt_float("Wear/damage (0.0 = pristine, 1.0 = destroyed):", default=0.6, min_val=0.0, max_val=1.0)
    args.extend(["--wear", str(wear)])

    return args


def prompt_floor():
    """Gather floor options and return CLI args list."""
    args = []

    variation = prompt_choice("Floor type:", FLOOR_VARIATIONS, default="concrete")
    args.extend(["--variation", variation])

    theme = prompt_choice("Theme:", THEMES, default="modern")
    args.extend(["--theme", theme])

    material = prompt_choice("Material override:", MATERIALS, default=None)
    if material:
        args.extend(["--material", material])

    width = prompt_float("Width (meters):", default=4.0, min_val=0.5, max_val=20.0)
    args.extend(["--width", str(width)])

    length = prompt_float("Length (meters):", default=4.0, min_val=0.5, max_val=20.0)
    args.extend(["--length", str(length)])

    wear = prompt_float("Wear/damage (0.0 = pristine, 1.0 = destroyed):", default=0.6, min_val=0.0, max_val=1.0)
    args.extend(["--wear", str(wear)])

    return args


ASSET_PROMPTERS = {
    "humanoid": prompt_humanoid,
    "wall": prompt_wall,
    "floor": prompt_floor,
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 56)
    print("   GameAssetGenerator3D — Interactive Asset Builder")
    print("=" * 56)

    # Step 1: Pick asset type
    asset_names = list(ASSETS.keys())
    print("\n  What would you like to generate?\n")
    for i, name in enumerate(asset_names, 1):
        desc = ASSETS[name]["description"]
        print(f"    {i}) {name:12s}  — {desc}")

    asset_type = None
    while asset_type is None:
        raw = input("\n  > ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(asset_names):
                asset_type = asset_names[idx - 1]
        except ValueError:
            if raw in ASSETS:
                asset_type = raw
        if asset_type is None:
            print(f"    Please enter 1-{len(asset_names)} or a name.")

    print(f"\n  Selected: {asset_type}")
    print("  " + "─" * 40)

    # Step 2: Asset-specific options
    prompter = ASSET_PROMPTERS[asset_type]
    extra_args = prompter()

    # Step 3: Output / export options
    print("\n── Export Settings ──")
    default_out = ASSETS[asset_type]["default_output"]
    output = prompt_string("Output file path:", default=default_out)

    fmt = prompt_choice("Export format:", EXPORT_FORMATS, default="glb")

    draco = prompt_yes_no("Enable Draco mesh compression?", default=False)

    # Build final command
    cmd = [
        sys.executable, "-m", "generator", "generate", asset_type,
        "-o", output,
        "-f", fmt,
    ]
    cmd.extend(extra_args)
    if draco:
        cmd.append("--draco")

    # Summary
    print("\n" + "=" * 56)
    print("  Ready to generate!")
    print(f"  Asset:  {asset_type}")
    print(f"  Output: {output}")
    print(f"  Format: {fmt}")
    print("=" * 56)

    # Show the equivalent CLI command
    display_cmd = " ".join(cmd)
    print(f"\n  Command: {display_cmd}\n")

    if not prompt_yes_no("Proceed?", default=True):
        print("  Cancelled.")
        sys.exit(0)

    print()
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        sys.exit(0)
