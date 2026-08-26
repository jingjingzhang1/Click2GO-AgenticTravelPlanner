"""ORM ↔ DTO / dict mapping for POIs and itineraries."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import POI
from ..schemas import ItineraryDaySchema, POISchema


def poi_orm_to_schema(poi: POI) -> POISchema:
    """ORM POI → transport DTO (used in API responses)."""
    return POISchema.model_validate(poi)


def poi_orm_to_dict(poi: POI, persona_tags: Optional[List[str]] = None) -> Dict:
    """
    ORM POI → plain dict for the agent/design layer (map + PDF generation).
    ``persona_tags`` lets callers inject the user's selected personas so map
    highlighting works without another DB round-trip.
    """
    return {
        "name": poi.name,
        "address": poi.address,
        "lat": poi.lat,
        "lng": poi.lng,
        "category": poi.category,
        "persona_score": poi.persona_score,
        "agent_note": poi.agent_note,
        "is_open": poi.is_open,
        "website": poi.website,
        "reservation_url": poi.reservation_url,
        "needs_reservation": bool(poi.needs_reservation),
        "transit_note": poi.transit_note,
        "persona_tags": persona_tags or [],
        "likes": poi.likes,
    }


def orm_to_itinerary_days(grouped: Dict[int, List[POI]]) -> List[ItineraryDaySchema]:
    """Grouped {day_number: [POI]} → ordered list of day DTOs."""
    return [
        ItineraryDaySchema(
            day_number=day_number,
            pois=[poi_orm_to_schema(p) for p in pois],
        )
        for day_number, pois in sorted(grouped.items())
    ]


def session_to_itinerary_dict(
    session_id: str,
    grouped: Dict[int, List[POI]],
    persona_tags: Optional[List[str]] = None,
    stats: Optional[Dict] = None,
) -> Dict:
    """Grouped POIs → the ``itinerary`` dict shape consumed by the Design Agent."""
    return {
        "session_id": session_id,
        "days": [
            [poi_orm_to_dict(p, persona_tags) for p in pois]
            for _, pois in sorted(grouped.items())
        ],
        "stats": stats or {},
    }
