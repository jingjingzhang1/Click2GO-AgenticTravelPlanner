from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PersonaType(str, Enum):
    PHOTOGRAPHY = "photography"
    CHILLING = "chilling"
    FOODIE = "foodie"
    EXERCISE = "exercise"


class UserConstraints(BaseModel):
    allergies: List[str] = []
    budget: Optional[str] = None
    accessibility: Optional[str] = None


class HotelInfo(BaseModel):
    """Where the traveller is staying — the plan is anchored around this."""
    name: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class PlanningRequest(BaseModel):
    destination: str = Field(..., description="Travel destination, e.g. 'New York'")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    personas: List[PersonaType] = Field(
        default=[PersonaType.CHILLING],
        description="One or more traveler styles",
    )
    constraints: UserConstraints = Field(default_factory=UserConstraints)
    hotel: Optional[HotelInfo] = Field(default=None, description="Your hotel / base")
    max_pois_per_day: int = Field(5, ge=1, le=20, description="Max stops per day")
    language: str = Field("en", description="Output language: 'en' or 'zh'")

    @field_validator("personas")
    @classmethod
    def at_least_one_persona(cls, v: List[PersonaType]) -> List[PersonaType]:
        if not v:
            raise ValueError("Select at least one travel style.")
        return v


class POISchema(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    category: Optional[str] = None
    likes: int = 0
    is_open: Optional[bool] = None
    seasonal_match: Optional[bool] = None
    persona_score: Optional[float] = None
    agent_note: Optional[str] = None
    website: Optional[str] = None
    reservation_url: Optional[str] = None
    needs_reservation: bool = False
    transit_note: Optional[str] = None
    day_number: Optional[int] = None
    stop_order: Optional[int] = None

    class Config:
        from_attributes = True


class ItineraryDaySchema(BaseModel):
    day_number: int
    date: Optional[str] = None
    pois: List[POISchema] = []


class PlanningSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str
    itinerary: Optional[List[ItineraryDaySchema]] = None
    hotel: Optional[HotelInfo] = None
    pdf_url: Optional[str] = None
    map_url: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class PlanningStatusResponse(BaseModel):
    session_id: str
    status: str
    progress_message: str
    total_pois_scraped: int = 0
    total_pois_verified: int = 0
    total_pois_included: int = 0
    error_message: Optional[str] = None
    result: Optional[PlanningSessionResponse] = None


# ── Chat schemas ─────────────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="User message to the Design Agent")


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    map_updated: bool = False
    pdf_updated: bool = False
    map_url: Optional[str] = None
    pdf_url: Optional[str] = None


# ── Journal schemas ──────────────────────────────────────────────────────────

class JournalEntryRequest(BaseModel):
    spot_name: str = Field(..., description="Which spot this memory is about")
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: Optional[str] = Field(None, description="Typed note")
    transcript: Optional[str] = Field(None, description="Voice-note transcript")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Personal 1–5 rating")


class JournalMediaSchema(BaseModel):
    id: int
    media_type: str
    url: str
    caption: Optional[str] = None


class JournalEntrySchema(BaseModel):
    id: int
    session_id: str
    spot_name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: Optional[str] = None
    transcript: Optional[str] = None
    rating: Optional[int] = None
    created_at: Optional[str] = None
    media: List[JournalMediaSchema] = []
