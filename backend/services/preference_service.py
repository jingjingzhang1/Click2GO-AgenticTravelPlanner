"""Preference service — save/retrieve reusable traveller profiles."""
from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from ..mappers import profile_to_dict
from ..repositories import ProfileRepository
from ..schemas import PlanningRequest
from .exceptions import NotFoundError


class PreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)

    def save(self, request: PlanningRequest) -> Dict:
        personas_str = ",".join(p.value for p in request.personas)
        profile = self.profiles.create(
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            personas=personas_str,
            allergies=request.constraints.allergies,
            budget=request.constraints.budget,
            language=request.language,
            hotel=request.hotel.model_dump() if request.hotel else None,
        )
        self.db.commit()
        self.db.refresh(profile)
        return {
            "id": profile.id,
            "destination": profile.destination,
            "personas": personas_str,
            "message": "Preferences saved successfully",
        }

    def get(self, profile_id: int) -> Dict:
        profile = self.profiles.get_by_id(profile_id)
        if not profile:
            raise NotFoundError(f"profile {profile_id}")
        return profile_to_dict(profile)
