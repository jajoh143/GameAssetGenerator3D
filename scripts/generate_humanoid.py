"""Top-level Blender script: generate a rigged, animated low-poly humanoid.

Usage:
    blender --background --python scripts/generate_humanoid.py -- [options]

Options:
    --output PATH         Output file (default: assets/humanoid.glb)
    --format FORMAT       Export format: glb, gltf, fbx, obj
    --preset NAME         Character preset: average, tall, short, child, brute, slender, kenney
    --build NAME          Body build: lean, average, stocky, heavy
    --skin-tone NAME      Skin tone name or R,G,B,A values
    --hair-style NAME     Hair style: none, buzzed, short, spiky, slicked, long, mohawk, ponytail
    --hair-color NAME     Hair color name or R,G,B,A values
    --clothing TYPES      Comma-separated clothing list (e.g. "short_sleeve,jeans")
    --clothing-color CLR  Single named/RGBA color OR item:color pairs (tshirt:red,pants:navy)
    --mustache            Add a mustache (color matches hair by default)
    --mustache-color CLR  Override mustache color (name or R,G,B,A)
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
    parser.add_argument("--gender", default="neutral",
                        help="Body gender (neutral, male, female)")
    parser.add_argument("--skin-tone", default="tan",
                        help="Skin tone name or R,G,B,A (e.g., 'tan' or '0.5,0.4,0.3,1.0')")

    # Hair
    parser.add_argument("--hair-style", default="short",
                        help="Hair style (none, buzzed, short, spiky, slicked, long, mohawk, ponytail)")
    parser.add_argument("--hair-color", default="brown",
                        help="Hair color name or R,G,B,A values")

    # Clothing
    parser.add_argument("--clothing", default="short_sleeve,jeans",
                        help="Comma-separated clothing types: short_sleeve, long_sleeve, v_neck, shorts, jeans")
    parser.add_argument("--clothing-color", default=None,
                        help="Single color (red) or per-item pairs (tshirt:red,pants:navy)")

    # Face accessories
    parser.add_argument("--mustache", action="store_true",
                        help="Add a mustache (color matches hair by default)")
    parser.add_argument("--mustache-color", default=None,
                        help="Override mustache color (name or R,G,B,A)")

    # Template mesh (always on by default; --procedural opts back to the old generator)
    parser.add_argument("--procedural", action="store_true",
                        help="Build body mesh procedurally instead of using the NBM template")
    parser.add_argument("--lod", default="mid",
                        choices=["very_low", "low", "mid"],
                        help="Template mesh LOD tier (only used with --use-template): "
                             "very_low (<300 faces), low (300-500), mid (500+)")

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

    # Export options
    parser.add_argument("--draco", action="store_true",
                        help="Enable Draco mesh compression for glTF/GLB")

    # Pipeline selection
    parser.add_argument("--blender", action="store_true",
                        help="Use the Blender pipeline (requires Blender). "
                             "Default is the pure-Python gltf_pipeline.")

    return parser.parse_args(argv)


def _parse_color_value(value):
    """Parse a color value — either a name or comma-separated RGBA."""
    if "," in value:
        parts = [float(x.strip()) for x in value.split(",")]
        if len(parts) == 3:
            parts.append(1.0)
        return tuple(parts)
    return value


def main():
    args = parse_args()

    # ── Pure-Python path (default when --blender is NOT set) ─────────────────
    if not args.blender:
        import sys as _sys
        import os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        from generators.humanoid.presets import resolve_config
        from generators.humanoid.gltf_pipeline import build_humanoid_glb

        def _parse_color_val(v):
            if v and "," in v:
                parts = [float(x.strip()) for x in v.split(",")]
                if len(parts) == 3:
                    parts.append(1.0)
                return tuple(parts)
            return v

        clothing_raw = getattr(args, "clothing", "short_sleeve,jeans") or "short_sleeve,jeans"
        clothing_list = [c.strip() for c in clothing_raw.split(",") if c.strip()]

        skin_raw = getattr(args, "skin_tone", "tan") or "tan"
        hair_color_raw = getattr(args, "hair_color", "brown") or "brown"
        anim_raw = getattr(args, "animations", "all") or "all"

        if anim_raw == "all":
            anim_cfg = "all"
        elif anim_raw in ("none", ""):
            anim_cfg = []
        else:
            anim_cfg = [a.strip() for a in anim_raw.split(",") if a.strip()]

        cfg = resolve_config(
            preset=getattr(args, "preset", "average") or "average",
            build=getattr(args, "build", "average") or "average",
            gender=getattr(args, "gender", "neutral") or "neutral",
            skin_tone=_parse_color_val(skin_raw),
            hair_style=getattr(args, "hair_style", "none") or "none",
            hair_color=_parse_color_val(hair_color_raw),
            use_template=True,
            lod=getattr(args, "lod", "mid") or "mid",
            overrides={"clothing": clothing_list, "animations": anim_cfg},
        )

        # Apply direct proportion overrides
        if getattr(args, "height", None) is not None:
            cfg["height"] = args.height
        if getattr(args, "shoulder_width", None) is not None:
            cfg["shoulder_width"] = args.shoulder_width
        if getattr(args, "hip_width", None) is not None:
            cfg["hip_width"] = args.hip_width

        output = _os.path.abspath(args.output)
        build_humanoid_glb(cfg, output)
        print(f"Done! Asset saved to: {output}")
        _sys.exit(0)

    # ── Blender path (only when --blender is explicitly set) ─────────────────

    # Parse clothing color: single color or "type:color,type:color" dict
    def _parse_clothing_color(raw):
        if raw is None:
            return None
        if ":" in raw:
            result = {}
            for pair in raw.split(","):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    result[k.strip()] = _parse_color_value(v.strip())
            return result
        return _parse_color_value(raw)

    # Build config dict
    config = {
        "preset": args.preset,
        "build": args.build,
        "gender": args.gender,
        "skin_tone": _parse_color_value(args.skin_tone),
        "hair_style": args.hair_style,
        "hair_color": _parse_color_value(args.hair_color),
        "clothing": [c.strip() for c in args.clothing.split(",") if c.strip()],
        "clothing_color": _parse_clothing_color(args.clothing_color),
        "mustache": args.mustache,
        "mustache_color": (_parse_color_value(args.mustache_color)
                           if args.mustache_color else None),
        "randomize": args.randomize,
        "use_template": not args.procedural,
        "lod": args.lod,
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

    # Signal to template_mesh.py that height was explicitly requested.
    # Without this flag the template mesh is imported at its natural dimensions.
    if args.height is not None:
        config["height_override"] = args.height

    mesh_src = "procedural" if args.procedural else f"template({args.lod})"
    print(f"Generating humanoid: preset={args.preset}, build={args.build}, "
          f"gender={args.gender}, skin={args.skin_tone}, "
          f"hair={args.hair_style}/{args.hair_color}, "
          f"clothing={args.clothing}, mustache={args.mustache}, "
          f"mesh={mesh_src}")
    armature = generate(config)
    print("Generation complete. Exporting...")

    output = os.path.abspath(args.output)
    export(output, args.format, draco=args.draco)
    print(f"Done! Asset saved to: {output}")


if __name__ == "__main__":
    main()
