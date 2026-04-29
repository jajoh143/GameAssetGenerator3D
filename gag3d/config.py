"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    openai_api_key: str | None
    openai_image_model: str
    trellis2_path: Path | None
    trellis2_python: str
    trellis2_model_id: str
    blender_path: str
    work_dir: Path

    @classmethod
    def from_env(cls) -> "Config":
        trellis2_path = os.environ.get("TRELLIS2_PATH")
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_image_model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            trellis2_path=Path(trellis2_path) if trellis2_path else None,
            trellis2_python=os.environ.get("TRELLIS2_PYTHON", "python"),
            trellis2_model_id=os.environ.get(
                "TRELLIS2_MODEL_ID", "microsoft/TRELLIS.2-4B"
            ),
            blender_path=os.environ.get("BLENDER_PATH", "blender"),
            work_dir=Path(os.environ.get("GAG3D_WORK_DIR", "assets/output")),
        )
