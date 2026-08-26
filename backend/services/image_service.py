"""
Image service
=============
Turns a completed planning session into a shareable travel poster. Loads the
itinerary via repositories, delegates rendering to the provider chain, then
normalises the result (inline bytes *or* remote URL) into a locally-served
asset under ``/outputs``.
"""
from __future__ import annotations

import os
from typing import Dict

from sqlalchemy.orm import Session

from ..models import SessionStatus
from ..observability import get_logger
from ..repositories import POIRepository, ProfileRepository, SessionRepository
from ..tools.image_generator import generate_travel_poster
from .exceptions import ConflictError, NotFoundError

logger = get_logger("click2go.image")

OUTPUTS_DIR = "outputs"
_MIME_EXT = {"image/png": "png", "image/webp": "webp", "image/jpeg": "jpg", "image/jpg": "jpg"}


class ImageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = SessionRepository(db)
        self.profiles = ProfileRepository(db)
        self.pois = POIRepository(db)

    def generate_poster(self, session_id: str, language: str = "en") -> Dict:
        session = self.sessions.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")
        if session.status != SessionStatus.COMPLETED:
            raise ConflictError(f"Session is not completed yet (status: {session.status})")

        itinerary_data = self._build_itinerary_data(session_id, session.user_profile_id)
        result = generate_travel_poster(language=language, itinerary_data=itinerary_data)

        if not result.get("success"):
            return {
                "session_id": session_id,
                "language": language,
                "image_url": None,
                "prompt_used": result.get("prompt_used", ""),
                "provider": result.get("provider"),
                "error": result.get("error", "Image generation failed"),
                "success": False,
            }

        local_url, warn = self._persist(session_id, language, result)
        logger.info("poster ready", extra={"session_id": session_id,
                                           "provider": result.get("provider")})
        return {
            "session_id": session_id,
            "language": language,
            "image_url": local_url,
            "prompt_used": result.get("prompt_used", ""),
            "provider": result.get("provider"),
            "error": warn,
            "success": True,
        }

    # ── helpers ─────────────────────────────────────────────────────────
    def _build_itinerary_data(self, session_id: str, profile_id) -> Dict:
        profile = self.profiles.get_by_id(profile_id) if profile_id else None
        destination = profile.destination if profile else "Unknown Destination"
        personas = [p.strip() for p in (profile.personas if profile else "travel").split(",")]

        grouped = self.pois.group_by_day(session_id)
        return {
            "destination": destination,
            "personas": personas,
            "days": [
                {"day_number": dn, "pois": [p.name for p in pois]}
                for dn, pois in sorted(grouped.items())
            ],
        }

    def _persist(self, session_id: str, language: str, result: Dict):
        """Save inline bytes or download a remote URL to /outputs."""
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        short = session_id[:8]
        ext = _MIME_EXT.get((result.get("mime_type") or "").lower(), "png")
        filename = f"poster_{short}_{language}.{ext}"
        save_path = os.path.join(OUTPUTS_DIR, filename)

        # Case 1: provider returned raw bytes (Gemini).
        if result.get("image_bytes"):
            try:
                with open(save_path, "wb") as f:
                    f.write(result["image_bytes"])
                return f"/outputs/{filename}", None
            except OSError as exc:
                return None, f"Could not write image ({exc})."

        # Case 2: provider returned a remote URL — cache it locally.
        image_url = result.get("image_url")
        try:
            import requests
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return f"/outputs/{filename}", None
        except Exception as exc:  # noqa: BLE001 — fall back to the direct URL
            return image_url, f"Could not cache image locally ({exc}); using direct URL."
