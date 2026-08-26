"""DAO for POI and ItineraryDay records tied to a planning session."""
from __future__ import annotations

from typing import Dict, List

from ..models import POI, ItineraryDay
from .base import BaseRepository


class POIRepository(BaseRepository[POI]):
    model = POI

    def routed_for_session(self, session_id: str) -> List[POI]:
        """Return routed POIs (day assigned) ordered for display."""
        return (
            self.db.query(POI)
            .filter(POI.session_id == session_id, POI.day_number.isnot(None))
            .order_by(POI.day_number, POI.stop_order)
            .all()
        )

    def group_by_day(self, session_id: str) -> Dict[int, List[POI]]:
        days: Dict[int, List[POI]] = {}
        for poi in self.routed_for_session(session_id):
            days.setdefault(poi.day_number or 1, []).append(poi)
        return dict(sorted(days.items()))

    def save_clustered_days(
        self,
        session_id: str,
        clustered_days: List[List[Dict]],
    ) -> None:
        """
        Persist a clustered itinerary: one POI row per stop plus an
        ItineraryDay summary row per day. Does not commit.
        """
        for day_idx, day_pois in enumerate(clustered_days):
            for stop_idx, p in enumerate(day_pois):
                self.db.add(POI(
                    session_id=session_id,
                    name=p.get("name", ""),
                    address=p.get("address"),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    category=p.get("category"),
                    likes=p.get("likes", 0),
                    source_url=p.get("source_url", ""),
                    raw_content=(p.get("raw_content") or "")[:2000],
                    website=p.get("website"),
                    reservation_url=p.get("reservation_url"),
                    needs_reservation=bool(p.get("needs_reservation", False)),
                    transit_note=p.get("transit_note"),
                    is_verified=True,
                    is_open=p.get("is_open"),
                    seasonal_match=p.get("seasonal_match"),
                    persona_score=p.get("persona_score"),
                    verification_recommendation=p.get("recommendation"),
                    agent_note=p.get("agent_note", ""),
                    day_number=day_idx + 1,
                    stop_order=stop_idx + 1,
                ))

            self.db.add(ItineraryDay(
                session_id=session_id,
                day_number=day_idx + 1,
                poi_sequence=[p.get("name") for p in day_pois],
            ))
