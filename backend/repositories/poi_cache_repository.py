"""DAO for the destination-level POI cache."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..models import POICache
from .base import BaseRepository

_CACHE_FIELDS = (
    "address", "lat", "lng", "category", "persona_tags", "persona_score",
    "is_open", "seasonal_info", "agent_note", "source_url", "raw_content", "likes",
    "website", "reservation_url", "needs_reservation",
)


class POICacheRepository(BaseRepository[POICache]):
    model = POICache

    def for_destination(self, destination: str) -> List[POICache]:
        return (
            self.db.query(POICache)
            .filter(POICache.destination == destination)
            .all()
        )

    def upsert_many(self, destination: str, pois: List[Dict]) -> int:
        """
        Insert new POIs or update existing ones (matched by destination+name).
        Returns the number of rows touched. Does not commit.
        """
        count = 0
        for p in pois:
            existing = (
                self.db.query(POICache)
                .filter(POICache.destination == destination, POICache.name == p["name"])
                .first()
            )
            if existing:
                for field in _CACHE_FIELDS:
                    if field in p:
                        setattr(existing, field, p[field])
                existing.verified_at = datetime.utcnow()
            else:
                self.db.add(POICache(
                    destination=destination,
                    name=p["name"],
                    persona_tags=p.get("persona_tags", []),
                    likes=p.get("likes", 0),
                    verified_at=datetime.utcnow(),
                    **{f: p.get(f) for f in _CACHE_FIELDS if f not in ("persona_tags", "likes")},
                ))
            count += 1
        return count

    def latest_verified_at(self, pois: List[POICache]) -> datetime | None:
        return max((p.verified_at for p in pois if p.verified_at), default=None)
