"""
Database Tools (agent-facing write API)
=======================================
Stable, function-style API used by the agents and tests. Each function owns a
short-lived unit of work (open session → mutate via a repository → commit) so
agents never hold long-lived sessions or issue raw SQL.

These are thin adapters over the repository (DAO) layer — the real query logic
lives in ``backend/repositories``. Keeping this facade means agent code and the
existing test-suite have a simple import surface while the persistence details
stay centralised and testable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from ..database import SessionLocal
from ..models import SessionStatus
from ..repositories import (
    ChatRepository,
    POICacheRepository,
    POIRepository,
    SessionRepository,
)


def upsert_poi_cache(destination: str, pois: List[Dict]) -> int:
    """Upsert verified POIs into the destination cache. Returns rows touched."""
    db = SessionLocal()
    try:
        count = POICacheRepository(db).upsert_many(destination, pois)
        db.commit()
        return count
    finally:
        db.close()


def get_cached_pois(destination: str, max_age_hours: int = 72) -> List[Dict]:
    """
    Retrieve cached POIs for a destination if fresh enough.
    Returns an empty list when the cache is stale or missing.
    """
    db = SessionLocal()
    try:
        repo = POICacheRepository(db)
        pois = repo.for_destination(destination)
        if not pois:
            return []

        latest = repo.latest_verified_at(pois)
        if latest and (datetime.utcnow() - latest).total_seconds() > max_age_hours * 3600:
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
                "website": p.website,
                "reservation_url": p.reservation_url,
                "needs_reservation": bool(p.needs_reservation),
                "recommendation": "INCLUDE",
            }
            for p in pois
        ]
    finally:
        db.close()


def save_session_pois(session_id: str, clustered_days: List[List[Dict]]) -> None:
    """Persist clustered POIs and itinerary days to the session."""
    db = SessionLocal()
    try:
        POIRepository(db).save_clustered_days(session_id, clustered_days)
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
        repo = SessionRepository(db)
        session = repo.get_by_id(session_id)
        if not session:
            return
        session.status = status
        if error_message:
            session.error_message = error_message
        if stats:
            repo.apply_stats(session, stats)
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
        ChatRepository(db).add_message(session_id, role, content, metadata)
        db.commit()
    finally:
        db.close()


def get_chat_history(session_id: str) -> List[Dict]:
    """Retrieve chat history for a session."""
    db = SessionLocal()
    try:
        return [
            {"role": m.role, "content": m.content}
            for m in ChatRepository(db).history(session_id)
        ]
    finally:
        db.close()
