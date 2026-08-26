"""
OpenRouter image provider
=========================
Reaches image-capable models (e.g. Google's ``gemini-2.5-flash-image`` — Nano
Banana, the best model at legible in-image text) through the OpenRouter
gateway using the OpenAI-compatible chat-completions endpoint with
``modalities: ["image", "text"]``. The generated image comes back on
``message.images[].image_url.url`` as a base64 data URL.

Uses the same key as the LLM (``OPENAI_API_KEY``) and is only active when
``OPENAI_BASE_URL`` points at OpenRouter.
"""
from __future__ import annotations

import base64
import logging

from ...config import settings
from .base import ImageProvider, ImageResult

logger = logging.getLogger(__name__)


class OpenRouterImageProvider(ImageProvider):
    name = "openrouter"

    def is_available(self) -> bool:
        base = (settings.openai_base_url or "").lower()
        return bool(settings.openai_api_key and settings.openai_api_key.strip()) and "openrouter" in base

    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        import requests

        url = settings.openai_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
            # Optional attribution headers OpenRouter recommends.
            "HTTP-Referer": "https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner",
            "X-Title": "Click2GO",
        }
        payload = {
            "model": settings.openrouter_image_model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        message = (data.get("choices") or [{}])[0].get("message", {})
        images = message.get("images") or []
        if not images:
            return ImageResult(
                success=False,
                provider=self.name,
                prompt_used=prompt,
                error="OpenRouter returned no image (model may not support image output "
                      "or the account is out of credits).",
            )

        image_url = images[0].get("image_url", {}).get("url", "")
        if image_url.startswith("data:"):
            b64 = image_url.split(",", 1)[1]
            return ImageResult(
                success=True,
                provider=self.name,
                prompt_used=prompt,
                image_bytes=base64.b64decode(b64),
                mime_type="image/png",
            )
        if image_url:
            return ImageResult(
                success=True,
                provider=self.name,
                prompt_used=prompt,
                image_url=image_url,
                mime_type="image/png",
            )

        return ImageResult(
            success=False,
            provider=self.name,
            prompt_used=prompt,
            error="OpenRouter image payload had no usable URL.",
        )
