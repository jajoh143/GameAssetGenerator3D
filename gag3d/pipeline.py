"""End-to-end pipeline: prompt|image → TRELLIS.2 → Blender (rig+animate) → GLB."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config
from .image_gen import FileImageSource, ImageRequest, OpenAIImageGenerator
from .mesh_gen import Trellis2LocalGenerator
from .prompts import build_humanoid_prompt, build_prop_prompt

BLENDER_JOB = Path(__file__).parent / "blender_jobs" / "rig_and_animate.py"

# A progress callback receives (stage, message). Stages:
#   "image", "image_done", "mesh", "mesh_done", "blender", "done"
ProgressFn = Callable[[str, str], None]


@dataclass
class GenerationRequest:
    asset_type: str            # "humanoid" | "prop"
    output_glb: Path
    prompt: str | None = None
    image: Path | None = None
    style: str | None = None
    animations: list[str] | None = None
    resolution: int = 1024
    normalize_height: float = 1.8
    keep_intermediates: bool = False


@dataclass
class GenerationResult:
    output_glb: Path
    image_path: Path
    raw_mesh_glb: Path


def run(
    request: GenerationRequest,
    config: Config,
    progress: ProgressFn | None = None,
) -> GenerationResult:
    progress = progress or (lambda _stage, _msg: None)
    if request.prompt is None and request.image is None:
        raise ValueError("Either --prompt or --image must be provided.")
    if request.asset_type not in ("humanoid", "prop"):
        raise ValueError(f"Unknown asset_type: {request.asset_type}")

    config.work_dir.mkdir(parents=True, exist_ok=True)
    stem = request.output_glb.stem
    image_path = config.work_dir / f"{stem}_input.png"
    raw_mesh = config.work_dir / f"{stem}_trellis.glb"

    # ─── 1. Image ────────────────────────────────────────────────────────
    if request.image is not None:
        progress("image", f"Using supplied image: {request.image.name}")
        image_path = FileImageSource(request.image).generate(ImageRequest(prompt=""))
    else:
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required for prompt-based generation.")
        progress("image", f"Generating reference image with {config.openai_image_model}…")
        if request.asset_type == "humanoid":
            text = build_humanoid_prompt(request.prompt, request.style or "low-poly stylized 3D, clean topology, game-asset look")
        else:
            text = build_prop_prompt(request.prompt, request.style or "stylized 3D game asset, PBR materials")
        gen = OpenAIImageGenerator(config.openai_api_key, config.openai_image_model)
        image_path = gen.generate(ImageRequest(prompt=text, output_path=image_path))
    progress("image_done", f"Image ready: {image_path}")

    # ─── 2. Mesh (TRELLIS.2) ─────────────────────────────────────────────
    if config.trellis2_path is None:
        raise RuntimeError("TRELLIS2_PATH not set; cannot run mesh generation.")
    progress("mesh", f"Running TRELLIS.2 inference at {request.resolution}³…")
    mesh_gen = Trellis2LocalGenerator(
        trellis2_path=config.trellis2_path,
        python_bin=config.trellis2_python,
        model_id=config.trellis2_model_id,
    )
    mesh_gen.generate(image_path, raw_mesh, resolution=request.resolution)
    progress("mesh_done", f"Mesh ready: {raw_mesh}")

    # ─── 3. Blender: rig + animate + export ──────────────────────────────
    animations = request.animations or (["idle", "walk", "run", "jump", "attack"] if request.asset_type == "humanoid" else [])
    if request.asset_type == "humanoid":
        progress("blender", f"Rigging + animating ({', '.join(animations) or 'no animations'})…")
    else:
        progress("blender", "Normalizing + exporting prop…")
    job = {
        "input_glb": str(raw_mesh.resolve()),
        "output_glb": str(request.output_glb.resolve()),
        "asset_type": request.asset_type,
        "animations": animations,
        "normalize_height": request.normalize_height,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(job, f)
        job_file = Path(f.name)

    try:
        result = subprocess.run(
            [config.blender_path, "--background", "--python", str(BLENDER_JOB), "--", str(job_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Blender job failed (exit {result.returncode}):\n"
                f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
            )
    finally:
        job_file.unlink(missing_ok=True)

    progress("done", f"Wrote {request.output_glb}")

    return GenerationResult(
        output_glb=request.output_glb,
        image_path=image_path,
        raw_mesh_glb=raw_mesh,
    )
