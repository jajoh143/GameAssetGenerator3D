"""Image source interface — provides a single front-facing reference image."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageRequest:
    prompt: str
    size: str = "1024x1024"
    background: str = "transparent"
    output_path: Path | None = None


class ImageGenerator(ABC):
    @abstractmethod
    def generate(self, request: ImageRequest) -> Path:
        """Return the path to a PNG image suitable for TRELLIS.2 input."""
