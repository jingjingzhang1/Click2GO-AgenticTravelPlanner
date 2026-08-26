"""ORM ↔ dict mapping for UserProfile."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import UserProfile


def profile_to_dict(profile: Optional[UserProfile]) -> Dict:
    """Full profile serialization for the preferences API."""
    if profile is None:
        return {}
    return {
        "id": profile.id,
        "destination": profile.destination,
        "start_date": profile.start_date,
        "end_date": profile.end_date,
        "personas": profile.personas,
        "allergies": profile.allergies,
        "budget": profile.budget,
        "language": profile.language,
        "hotel": {
            "name": profile.hotel_name,
            "address": profile.hotel_address,
            "lat": profile.hotel_lat,
            "lng": profile.hotel_lng,
        },
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }


def profile_to_summary(profile: Optional[UserProfile], personas_fallback: str = "chilling") -> Dict:
    """Compact profile shape consumed by the Design Agent (map/PDF header)."""
    if profile is None:
        return {
            "destination": "Unknown",
            "start_date": "",
            "end_date": "",
            "persona": personas_fallback,
            "personas": [personas_fallback],
        }
    personas_list: List[str] = (
        profile.personas.split(",") if profile.personas else [personas_fallback]
    )
    return {
        "destination": profile.destination,
        "start_date": profile.start_date or "",
        "end_date": profile.end_date or "",
        "persona": profile.personas or personas_fallback,
        "personas": personas_list,
    }
