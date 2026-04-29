"""Mesh generator interface — image → static GLB."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class MeshGenerator(ABC):
    @abstractmethod
    def generate(self, image_path: Path, output_glb: Path, resolution: int = 1024) -> Path:
        """Read image_path, write a textured GLB to output_glb, return output_glb."""
