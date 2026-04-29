"""OpenAI Images adapter (gpt-image-1)."""

from __future__ import annotations

import base64
from pathlib import Path

from .base import ImageGenerator, ImageRequest


class OpenAIImageGenerator(ImageGenerator):
    def __init__(self, api_key: str, model: str = "gpt-image-1"):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, request: ImageRequest) -> Path:
        if request.output_path is None:
            raise ValueError("output_path is required for OpenAIImageGenerator")

        response = self.client.images.generate(
            model=self.model,
            prompt=request.prompt,
            size=request.size,
            background=request.background,
            n=1,
        )

        b64 = response.data[0].b64_json
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(base64.b64decode(b64))
        return request.output_path
