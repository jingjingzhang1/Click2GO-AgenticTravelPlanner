"""DAO for UserProfile aggregate."""
from __future__ import annotations

from typing import List, Optional

from ..models import UserProfile
from .base import BaseRepository


class ProfileRepository(BaseRepository[UserProfile]):
    model = UserProfile

    def create(
        self,
        *,
        destination: str,
        start_date: Optional[str],
        end_date: Optional[str],
        personas: str,
        allergies: List[str],
        budget: Optional[str],
        language: str = "en",
        hotel: Optional[dict] = None,
    ) -> UserProfile:
        """Build and stage a new profile (no commit)."""
        hotel = hotel or {}
        profile = UserProfile(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            personas=personas,
            allergies=allergies,
            budget=budget,
            language=language,
            hotel_name=hotel.get("name"),
            hotel_address=hotel.get("address"),
            hotel_lat=hotel.get("lat"),
            hotel_lng=hotel.get("lng"),
        )
        self.db.add(profile)
        return profile

    def get_by_id(self, profile_id: int) -> Optional[UserProfile]:
        return self.get(profile_id)
