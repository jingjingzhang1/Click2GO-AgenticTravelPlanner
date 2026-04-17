import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class PersonaType(str, enum.Enum):
    PHOTOGRAPHY = "photography"
    CHILLING = "chilling"
    FOODIE = "foodie"
    EXERCISE = "exercise"


class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    SCRAPING = "scraping"
    VERIFYING = "verifying"
    ROUTING = "routing"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    destination = Column(String(200), nullable=False)
    start_date = Column(String(20))
    end_date = Column(String(20))
    personas = Column(String(200), default=PersonaType.CHILLING)
    allergies = Column(JSON, default=list)
    budget = Column(String(50))
    language = Column(String(10), default="en")
    created_at = Column(DateTime, server_default=func.now())

    sessions = relationship("PlanningSession", back_populates="user_profile")


class PlanningSession(Base):
    __tablename__ = "planning_sessions"

    id = Column(String(36), primary_key=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"))
    status = Column(String(50), default=SessionStatus.PENDING)
    total_pois_scraped = Column(Integer, default=0)
    total_pois_verified = Column(Integer, default=0)
    total_pois_included = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    user_profile = relationship("UserProfile", back_populates="sessions")
    pois = relationship("POI", back_populates="session")
    itinerary_days = relationship("ItineraryDay", back_populates="session")
    chat_messages = relationship("ChatMessage", back_populates="session")


class POI(Base):
    __tablename__ = "pois"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("planning_sessions.id"))
    name = Column(String(500))
    address = Column(String(1000), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    category = Column(String(100), nullable=True)
    likes = Column(Integer, default=0)
    source_url = Column(String(500), nullable=True)
    raw_content = Column(Text, nullable=True)

    # Verification
    is_verified = Column(Boolean, default=False)
    is_open = Column(Boolean, nullable=True)
    seasonal_match = Column(Boolean, nullable=True)
    persona_score = Column(Float, nullable=True)
    verification_recommendation = Column(String(10), nullable=True)
    agent_note = Column(Text, nullable=True)

    # Routing
    day_number = Column(Integer, nullable=True)
    stop_order = Column(Integer, nullable=True)

    session = relationship("PlanningSession", back_populates="pois")


class ItineraryDay(Base):
    __tablename__ = "itinerary_days"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("planning_sessions.id"))
    day_number = Column(Integer)
    date = Column(String(20), nullable=True)
    poi_sequence = Column(JSON)
    cluster_center_lat = Column(Float, nullable=True)
    cluster_center_lng = Column(Float, nullable=True)

    session = relationship("PlanningSession", back_populates="itinerary_days")


class POICache(Base):
    """
    Destination-level POI cache managed by the Knowledge Manager agent.
    Stores verified POIs so repeat queries for popular cities are instant.
    """
    __tablename__ = "poi_cache"

    id = Column(Integer, primary_key=True, index=True)
    destination = Column(String(200), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    address = Column(String(1000), nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    category = Column(String(100), nullable=True)
    persona_tags = Column(JSON, default=list)
    persona_score = Column(Float, nullable=True)
    is_open = Column(Boolean, nullable=True)
    seasonal_info = Column(Text, nullable=True)
    agent_note = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)
    raw_content = Column(Text, nullable=True)
    likes = Column(Integer, default=0)
    scraped_at = Column(DateTime, server_default=func.now())
    verified_at = Column(DateTime, nullable=True)


class ChatMessage(Base):
    """Chat history for interactive Design Agent sessions."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("planning_sessions.id"))
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("PlanningSession", back_populates="chat_messages")
