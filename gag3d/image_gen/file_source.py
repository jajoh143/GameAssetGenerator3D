"""Pass-through 'image source' that returns a user-supplied file."""

from __future__ import annotations

from pathlib import Path

from .base import ImageGenerator, ImageRequest


class FileImageSource(ImageGenerator):
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Image not found: {self.path}")

    def generate(self, request: ImageRequest) -> Path:
        return self.path
