"""Image-provider strategy interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ImageResult:
    """
    Uniform return type across providers.

    A provider may return either raw ``image_bytes`` (Gemini, which streams the
    image inline) or a remote ``image_url`` (Replicate/Pollinations). The
    service layer normalises both into a locally-served asset.
    """
    success: bool
    provider: str
    prompt_used: str
    image_bytes: Optional[bytes] = None
    image_url: Optional[str] = None
    mime_type: str = "image/png"
    error: Optional[str] = None


class ImageProvider(ABC):
    """Base class for all travel-poster image providers."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured (has credentials, etc.)."""

    @abstractmethod
    def generate(self, prompt: str, width: int, height: int) -> ImageResult:
        """Generate an image for ``prompt`` or raise on failure."""
