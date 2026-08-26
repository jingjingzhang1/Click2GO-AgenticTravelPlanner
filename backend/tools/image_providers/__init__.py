"""
Image-provider registry
========================
Providers are selected at runtime by the ``IMAGE_PROVIDER_PRIORITY`` setting
(e.g. ``gemini,replicate,pollinations``). The generator walks the list in
order and uses the first provider that is both configured and succeeds — the
classic strategy + chain-of-responsibility pattern.
"""
from __future__ import annotations

from typing import Dict, List

from ...config import settings
from .base import ImageProvider, ImageResult
from .gemini_provider import GeminiImageProvider
from .openai_provider import OpenAIImageProvider
from .openrouter_provider import OpenRouterImageProvider
from .pollinations_provider import PollinationsImageProvider
from .replicate_provider import ReplicateImageProvider

_REGISTRY: Dict[str, type[ImageProvider]] = {
    OpenRouterImageProvider.name: OpenRouterImageProvider,
    GeminiImageProvider.name: GeminiImageProvider,
    OpenAIImageProvider.name: OpenAIImageProvider,
    ReplicateImageProvider.name: ReplicateImageProvider,
    PollinationsImageProvider.name: PollinationsImageProvider,
}


def ordered_providers() -> List[ImageProvider]:
    """Instantiate providers in the configured priority order."""
    providers: List[ImageProvider] = []
    for name in settings.image_providers:
        cls = _REGISTRY.get(name)
        if cls:
            providers.append(cls())
    # Guarantee at least the keyless fallback is present.
    if not any(isinstance(p, PollinationsImageProvider) for p in providers):
        providers.append(PollinationsImageProvider())
    return providers


__all__ = [
    "ImageProvider",
    "ImageResult",
    "OpenRouterImageProvider",
    "GeminiImageProvider",
    "OpenAIImageProvider",
    "ReplicateImageProvider",
    "PollinationsImageProvider",
    "ordered_providers",
]
