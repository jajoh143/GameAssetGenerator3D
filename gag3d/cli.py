"""CLI entry point: ``python -m gag3d``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .pipeline import GenerationRequest, run


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gag3d",
        description="Generate rigged, animated 3D game assets via TRELLIS.2.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate one asset.")
    g.add_argument("asset_type", choices=["humanoid", "prop"])
    g.add_argument("-o", "--output", type=Path, required=True, help="Output GLB path.")

    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt", type=str, help="Text prompt for OpenAI image generation.")
    src.add_argument("--image", type=Path, help="Existing reference image (PNG, front-facing).")

    g.add_argument("--style", type=str, default=None, help="Visual style modifier for the prompt.")
    g.add_argument("--animations", type=str, default=None,
                   help="Comma-separated animation names (humanoid only). "
                        "Default: idle,walk,run,jump,attack.")
    g.add_argument("--resolution", type=int, default=1024,
                   help="TRELLIS.2 voxel resolution: 512 / 1024 / 1536.")
    g.add_argument("--height", type=float, default=1.8,
                   help="Normalized output height in meters (humanoid: 1.8, prop: 1.0).")
    g.add_argument("--keep-intermediates", action="store_true",
                   help="Retain the source image and raw TRELLIS GLB next to the output.")

    sub.add_parser("doctor", help="Diagnose environment configuration.")

    return p


def cmd_generate(args: argparse.Namespace) -> int:
    config = Config.from_env()
    animations = None
    if args.animations:
        animations = [a.strip() for a in args.animations.split(",") if a.strip()]

    request = GenerationRequest(
        asset_type=args.asset_type,
        output_glb=args.output,
        prompt=args.prompt,
        image=args.image,
        style=args.style,
        animations=animations,
        resolution=args.resolution,
        normalize_height=args.height if args.asset_type == "humanoid" else min(args.height, 1.0),
        keep_intermediates=args.keep_intermediates,
    )

    result = run(request, config)
    print(f"✓ Wrote {result.output_glb}")
    print(f"  source image:   {result.image_path}")
    print(f"  raw TRELLIS GLB: {result.raw_mesh_glb}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    config = Config.from_env()
    print(f"OPENAI_API_KEY:      {'set' if config.openai_api_key else 'MISSING'}")
    print(f"OPENAI_IMAGE_MODEL:  {config.openai_image_model}")
    print(f"TRELLIS2_PATH:       {config.trellis2_path or 'MISSING'}")
    print(f"TRELLIS2_PYTHON:     {config.trellis2_python}")
    print(f"TRELLIS2_MODEL_ID:   {config.trellis2_model_id}")
    print(f"BLENDER_PATH:        {config.blender_path}")
    print(f"GAG3D_WORK_DIR:      {config.work_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        return cmd_generate(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
