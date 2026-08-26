"""
Preferences Router (thin controller)
====================================
POST /api/v1/preferences          – save a user preference profile
GET  /api/v1/preferences/{id}     – retrieve a saved profile
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import PlanningRequest
from ..services.preference_service import PreferenceService

router = APIRouter()


@router.post("/preferences", status_code=201)
async def save_preferences(request: PlanningRequest, db: Session = Depends(get_db)):
    """Persist a traveller preference profile for reuse across sessions."""
    return PreferenceService(db).save(request)


@router.get("/preferences/{profile_id}")
async def get_preferences(profile_id: int, db: Session = Depends(get_db)):
    """Retrieve a previously saved traveller profile."""
    return PreferenceService(db).get(profile_id)
