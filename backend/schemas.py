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
    budget: Optional[str] = None      # "budget" | "mid-range" | "luxury"
    accessibility: Optional[str] = None


class PlanningRequest(BaseModel):
    destination: str = Field(..., description="Travel destination, e.g. 'Tokyo' or '东京'")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    personas: List[PersonaType] = Field(
        default=[PersonaType.CHILLING],
        description="One or more traveler styles",
    )
    constraints: UserConstraints = Field(default_factory=UserConstraints)
    max_pois_per_day: int = Field(5, ge=1, le=10, description="Max stops per day")
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
