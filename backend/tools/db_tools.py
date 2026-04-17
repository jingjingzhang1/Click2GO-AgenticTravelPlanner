"""
Database Tools (ORM Write Layer)
================================
Safe SQLAlchemy ORM functions for writing data to PostgreSQL.
Used exclusively by agents for INSERT/UPDATE operations,
ensuring no LLM-hallucinated SQL mutations.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import (
    ChatMessage,
    ItineraryDay,
    POI,
    POICache,
    PlanningSession,
    SessionStatus,
)


def upsert_poi_cache(
    destination: str,
    pois: List[Dict],
) -> int:
    """
    Upsert verified POIs into the destination cache.
    Returns the number of POIs upserted.
    """
    db = SessionLocal()
    try:
        count = 0
        for p in pois:
            existing = (
                db.query(POICache)
                .filter(
                    POICache.destination == destination,
                    POICache.name == p["name"],
                )
                .first()
            )
            if existing:
                existing.address = p.get("address", existing.address)
                existing.lat = p.get("lat", existing.lat)
                existing.lng = p.get("lng", existing.lng)
                existing.category = p.get("category", existing.category)
                existing.persona_tags = p.get("persona_tags", existing.persona_tags)
                existing.persona_score = p.get("persona_score", existing.persona_score)
                existing.is_open = p.get("is_open", existing.is_open)
                existing.seasonal_info = p.get("seasonal_info", existing.seasonal_info)
                existing.agent_note = p.get("agent_note", existing.agent_note)
                existing.source_url = p.get("source_url", existing.source_url)
                existing.raw_content = p.get("raw_content", existing.raw_content)
                existing.likes = p.get("likes", existing.likes)
                existing.verified_at = datetime.utcnow()
            else:
                db.add(POICache(
                    destination=destination,
                    name=p["name"],
                    address=p.get("address"),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    category=p.get("category"),
                    persona_tags=p.get("persona_tags", []),
                    persona_score=p.get("persona_score"),
                    is_open=p.get("is_open"),
                    seasonal_info=p.get("seasonal_info"),
                    agent_note=p.get("agent_note"),
                    source_url=p.get("source_url"),
                    raw_content=p.get("raw_content"),
                    likes=p.get("likes", 0),
                    verified_at=datetime.utcnow(),
                ))
            count += 1
        db.commit()
        return count
    finally:
        db.close()


def get_cached_pois(
    destination: str,
    max_age_hours: int = 72,
) -> List[Dict]:
    """
    Retrieve cached POIs for a destination if they are fresh enough.
    Returns empty list if cache is stale or missing.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow()
        pois = (
            db.query(POICache)
            .filter(POICache.destination == destination)
            .all()
        )
        if not pois:
            return []

        # Check freshness — use the most recent verified_at
        latest = max(
            (p.verified_at for p in pois if p.verified_at),
            default=None,
        )
        if latest and (cutoff - latest).total_seconds() > max_age_hours * 3600:
            return []

        return [
            {
                "name": p.name,
                "address": p.address,
                "lat": p.lat,
                "lng": p.lng,
                "category": p.category,
                "persona_tags": p.persona_tags or [],
                "persona_score": p.persona_score,
                "is_open": p.is_open,
                "seasonal_info": p.seasonal_info,
                "agent_note": p.agent_note,
                "source_url": p.source_url,
                "raw_content": p.raw_content,
                "likes": p.likes or 0,
                "recommendation": "INCLUDE",
            }
            for p in pois
        ]
    finally:
        db.close()


def save_session_pois(
    session_id: str,
    clustered_days: List[List[Dict]],
) -> None:
    """Persist clustered POIs and itinerary days to the session."""
    db = SessionLocal()
    try:
        for day_idx, day_pois in enumerate(clustered_days):
            for stop_idx, p in enumerate(day_pois):
                db.add(POI(
                    session_id=session_id,
                    name=p.get("name", ""),
                    address=p.get("address"),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    category=p.get("category"),
                    likes=p.get("likes", 0),
                    source_url=p.get("source_url", ""),
                    raw_content=(p.get("raw_content") or "")[:2000],
                    is_verified=True,
                    is_open=p.get("is_open"),
                    seasonal_match=p.get("seasonal_match"),
                    persona_score=p.get("persona_score"),
                    verification_recommendation=p.get("recommendation"),
                    agent_note=p.get("agent_note", ""),
                    day_number=day_idx + 1,
                    stop_order=stop_idx + 1,
                ))

            db.add(ItineraryDay(
                session_id=session_id,
                day_number=day_idx + 1,
                poi_sequence=[p.get("name") for p in day_pois],
            ))

        db.commit()
    finally:
        db.close()


def update_session_status(
    session_id: str,
    status: str,
    error_message: Optional[str] = None,
    stats: Optional[Dict] = None,
) -> None:
    """Update planning session status and stats."""
    db = SessionLocal()
    try:
        session = db.query(PlanningSession).filter(
            PlanningSession.id == session_id
        ).first()
        if not session:
            return

        session.status = status
        if error_message:
            session.error_message = error_message
        if stats:
            session.total_pois_scraped = stats.get("total_scraped", session.total_pois_scraped)
            session.total_pois_verified = stats.get("total_verified", session.total_pois_verified)
            session.total_pois_included = stats.get("total_included", session.total_pois_included)
        if status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
            session.completed_at = datetime.utcnow()

        db.commit()
    finally:
        db.close()


def save_chat_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None,
) -> None:
    """Persist a chat message for a session."""
    db = SessionLocal()
    try:
        db.add(ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            metadata_=metadata,
        ))
        db.commit()
    finally:
        db.close()


def get_chat_history(session_id: str) -> List[Dict]:
    """Retrieve chat history for a session."""
    db = SessionLocal()
    try:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
    finally:
        db.close()
