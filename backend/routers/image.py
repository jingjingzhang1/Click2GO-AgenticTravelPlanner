"""
Image Router
============
POST /api/v1/plan/{session_id}/generate-image
    Body: { "language": "en" | "zh" }
    Returns: { "image_url": str | null, "prompt_used": str, "error": str | null }
"""
import os
from typing import Dict, List, Literal, Optional

import requests as _requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import POI, PlanningSession, SessionStatus, UserProfile
from ..tools.image_generator import generate_travel_poster

router = APIRouter()


class ImageRequest(BaseModel):
    language: Literal["en", "zh"] = "en"


class ImageResponse(BaseModel):
    session_id: str
    language: str
    image_url: Optional[str] = None
    prompt_used: str = ""
    error: Optional[str] = None
    success: bool


@router.post("/plan/{session_id}/generate-image", response_model=ImageResponse)
async def generate_image(
    session_id: str,
    body: ImageRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a cartoon travel poster for a completed planning session.
    Fetches the image from Pollinations AI and serves it from /outputs/
    so the browser loads it from localhost (no external URL issues).
    """
    # ── Validate session ──────────────────────────────────────────────────────
    session = db.query(PlanningSession).filter(PlanningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")
    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not completed yet (status: {session.status})",
        )

    # ── Fetch profile & itinerary ─────────────────────────────────────────────
    profile = db.query(UserProfile).filter(UserProfile.id == session.user_profile_id).first()
    destination = profile.destination if profile else "Unknown Destination"
    personas    = [p.strip() for p in (profile.persona or "travel").split(",")]

    pois = (
        db.query(POI)
        .filter(POI.session_id == session_id, POI.day_number.isnot(None))
        .order_by(POI.day_number, POI.stop_order)
        .all()
    )

    days_map: Dict[int, List[str]] = {}
    for poi in pois:
        dn = poi.day_number or 1
        days_map.setdefault(dn, []).append(poi.name)

    itinerary_data = {
        "destination": destination,
        "personas":    personas,
        "days": [
            {"day_number": dn, "pois": names}
            for dn, names in sorted(days_map.items())
        ],
    }

    # ── Build Pollinations URL ────────────────────────────────────────────────
    result = generate_travel_poster(
        language       = body.language,
        itinerary_data = itinerary_data,
    )

    if not result.get("success") or not result.get("image_url"):
        return ImageResponse(
            session_id  = session_id,
            language    = body.language,
            prompt_used = result.get("prompt_used", ""),
            error       = result.get("error", "Failed to build image URL"),
            success     = False,
        )

    pollinations_url = result["image_url"]

    # ── Fetch image from Pollinations and save locally ────────────────────────
    short_id  = session_id[:8]
    lang_tag  = body.language
    filename  = f"poster_{short_id}_{lang_tag}.jpg"
    save_path = os.path.join("outputs", filename)

    try:
        resp = _requests.get(pollinations_url, timeout=60)
        resp.raise_for_status()
        os.makedirs("outputs", exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        local_url = f"/outputs/{filename}"
    except Exception as exc:
        # Fall back to returning the direct Pollinations URL
        local_url = pollinations_url
        result["error"] = f"Could not cache image locally ({exc}); using direct URL."

    return ImageResponse(
        session_id  = session_id,
        language    = body.language,
        image_url   = local_url,
        prompt_used = result.get("prompt_used", ""),
        error       = result.get("error"),
        success     = True,
    )
