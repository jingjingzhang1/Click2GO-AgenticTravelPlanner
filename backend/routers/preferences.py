"""
Preferences Router
==================
POST /api/v1/preferences          – save a user preference profile
GET  /api/v1/preferences/{id}     – retrieve a saved profile
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UserProfile
from ..schemas import PlanningRequest

router = APIRouter()


@router.post("/preferences", status_code=201)
async def save_preferences(request: PlanningRequest, db: Session = Depends(get_db)):
    """Persist a traveller preference profile for reuse across sessions."""
    profile = UserProfile(
        destination = request.destination,
        start_date  = request.start_date,
        end_date    = request.end_date,
        persona     = request.persona.value,
        allergies   = request.constraints.allergies,
        budget      = request.constraints.budget,
        language    = request.language,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "id":          profile.id,
        "destination": profile.destination,
        "persona":     profile.persona,
        "message":     "Preferences saved successfully",
    }


@router.get("/preferences/{profile_id}")
async def get_preferences(profile_id: int, db: Session = Depends(get_db)):
    """Retrieve a previously saved traveller profile."""
    profile = db.query(UserProfile).filter(UserProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id":          profile.id,
        "destination": profile.destination,
        "start_date":  profile.start_date,
        "end_date":    profile.end_date,
        "persona":     profile.persona,
        "allergies":   profile.allergies,
        "budget":      profile.budget,
        "language":    profile.language,
        "created_at":  profile.created_at.isoformat() if profile.created_at else None,
    }
