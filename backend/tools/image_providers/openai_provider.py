"""
OpenAI image provider (gpt-image-1)
===================================
Lets the same OPENAI_API_KEY that powers POI verification also render the
travel poster. gpt-image-1 is strong at legible in-image text, so it's a good
alternative to Gemini when you only want to manage one key.

Note: gpt-image-1 may require organization verification on your OpenAI account;
if the call fails, the provider chain falls through to the next provider.
"""
from __future__ import annotations

import base64
import logging

from ...config import settings
from .base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class OpenAIImageProvider(ImageProvider):
    name = "openai"

    def is_available(self) -> bool:
        return bool(settings.openai_api_key and settings.openai_api_key.strip())

    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        result = client.images.generate(
            model=settings.openai_image_model,
            prompt=prompt,
            size=self._nearest_size(width, height),
        )

        item = result.data[0]
        b64 = getattr(item, "b64_json", None)
        if b64:
            return ImageResult(
                success=True,
                provider=self.name,
                prompt_used=prompt,
                image_bytes=base64.b64decode(b64),
                mime_type="image/png",
            )

        url = getattr(item, "url", None)
        if url:
            return ImageResult(
                success=True,
                provider=self.name,
                prompt_used=prompt,
                image_url=url,
                mime_type="image/png",
            )

        return ImageResult(
            success=False,
            provider=self.name,
            prompt_used=prompt,
            error="OpenAI returned no image data.",
        )

    @staticmethod
    def _nearest_size(width: int, height: int) -> str:
        """Map to the sizes gpt-image-1 supports."""
        if width == height:
            return "1024x1024"
        return "1536x1024" if width > height else "1024x1536"
