"""
Image Router (thin controller)
==============================
POST /api/v1/plan/{session_id}/generate-image
    Body:    { "language": "en" | "zh" }
    Returns: { image_url, provider, prompt_used, error, success }

Generates a stylized travel poster for a completed session using the provider
chain (Gemini 2.5 Flash Image → Replicate → Pollinations).
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.image_service import ImageService

router = APIRouter()


class ImageRequest(BaseModel):
    language: Literal["en", "zh"] = "en"


class ImageResponse(BaseModel):
    session_id: str
    language: str
    image_url: Optional[str] = None
    provider: Optional[str] = None
    prompt_used: str = ""
    error: Optional[str] = None
    success: bool


@router.post("/plan/{session_id}/generate-image", response_model=ImageResponse)
async def generate_image(
    session_id: str,
    body: ImageRequest,
    db: Session = Depends(get_db),
):
    """Render the travel poster for a completed planning session."""
    result = ImageService(db).generate_poster(session_id, body.language)
    return ImageResponse(**result)
