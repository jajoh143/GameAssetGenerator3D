"""TRELLIS.2 local adapter.

TRELLIS.2 ships its own conda environment with CUDA-specific deps
(flash-attn, nvdiffrast, etc.) that don't coexist cleanly with the rest of
this project. Rather than import it in-process, we shell out to a worker
script that runs inside the TRELLIS.2 environment.

Required environment:
  TRELLIS2_PATH    — path to the cloned microsoft/TRELLIS.2 repo
  TRELLIS2_PYTHON  — python interpreter inside the TRELLIS.2 conda env
                     (e.g. /opt/conda/envs/trellis2/bin/python)
  TRELLIS2_MODEL_ID — defaults to "microsoft/TRELLIS.2-4B"
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import MeshGenerator

WORKER_SCRIPT = Path(__file__).with_name("trellis2_worker.py")


class Trellis2LocalGenerator(MeshGenerator):
    def __init__(
        self,
        trellis2_path: Path,
        python_bin: str = "python",
        model_id: str = "microsoft/TRELLIS.2-4B",
    ):
        self.trellis2_path = Path(trellis2_path)
        self.python_bin = python_bin
        self.model_id = model_id

        if not self.trellis2_path.exists():
            raise FileNotFoundError(
                f"TRELLIS2_PATH does not exist: {self.trellis2_path}"
            )

    def generate(self, image_path: Path, output_glb: Path, resolution: int = 1024) -> Path:
        output_glb.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "image": str(image_path.resolve()),
            "output": str(output_glb.resolve()),
            "model_id": self.model_id,
            "resolution": resolution,
        }

        result = subprocess.run(
            [self.python_bin, str(WORKER_SCRIPT)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=self.trellis2_path,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"TRELLIS.2 worker failed (exit {result.returncode}):\n"
                f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
            )

        if not output_glb.exists():
            raise RuntimeError(
                f"TRELLIS.2 worker reported success but {output_glb} is missing."
            )

        return output_glb
