"""
Gemini 2.5 Flash Image ("Nano Banana") provider
================================================
Google's ``gemini-2.5-flash-image`` model is state-of-the-art at rendering
legible text *inside* generated images — ideal for a travel poster whose
title, day labels, and highlight captions must be readable. The model streams
the image back inline as bytes on ``part.inline_data.data``.

Docs: https://ai.google.dev/gemini-api/docs/image-generation
"""
from __future__ import annotations

import logging

from ...config import settings
from .base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class GeminiImageProvider(ImageProvider):
    name = "gemini"

    def is_available(self) -> bool:
        return bool(settings.gemini_api_key and settings.gemini_api_key.strip())

    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        # Imported lazily so the dependency is optional at install time.
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=settings.gemini_api_key)

        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes, mime = self._extract_image(response)
        if not image_bytes:
            return ImageResult(
                success=False,
                provider=self.name,
                prompt_used=prompt,
                error="Gemini returned no image data (possibly safety-filtered).",
            )

        return ImageResult(
            success=True,
            provider=self.name,
            prompt_used=prompt,
            image_bytes=image_bytes,
            mime_type=mime,
        )

    @staticmethod
    def _extract_image(response) -> tuple[bytes | None, str]:
        """Pull the first inline image out of the model response."""
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    return inline.data, getattr(inline, "mime_type", "image/png")
        return None, "image/png"
