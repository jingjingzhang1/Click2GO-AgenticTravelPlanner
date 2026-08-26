"""Pollinations provider (free, no-auth final fallback)."""
from __future__ import annotations

from urllib.parse import quote

from .base import ImageProvider, ImageResult


class PollinationsImageProvider(ImageProvider):
    name = "pollinations"

    def is_available(self) -> bool:
        # Free and keyless — always available as the last-resort fallback.
        return True

    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        encoded = quote(prompt, safe="")
        seed = abs(hash(prompt)) % 99991
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
        )
        return ImageResult(
            success=True,
            provider=self.name,
            prompt_used=prompt,
            image_url=image_url,
            mime_type="image/jpeg",
        )
