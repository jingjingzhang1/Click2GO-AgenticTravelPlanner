"""Replicate FLUX Schnell provider (fallback)."""
from __future__ import annotations

import logging

from ...config import settings
from .base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class ReplicateImageProvider(ImageProvider):
    name = "replicate"

    def is_available(self) -> bool:
        return bool(settings.replicate_api_token and settings.replicate_api_token.strip())

    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        import replicate  # type: ignore

        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt,
                "go_fast": True,
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "webp",
                "output_quality": 90,
            },
        )
        if not output:
            return ImageResult(
                success=False,
                provider=self.name,
                prompt_used=prompt,
                error="Replicate returned no output.",
            )
        return ImageResult(
            success=True,
            provider=self.name,
            prompt_used=prompt,
            image_url=str(output[0]),
            mime_type="image/webp",
        )
