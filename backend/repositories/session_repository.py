"""DAO for PlanningSession aggregate."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..models import PlanningSession, SessionStatus
from .base import BaseRepository


class SessionRepository(BaseRepository[PlanningSession]):
    model = PlanningSession

    def create(self, session_id: str, user_profile_id: Optional[int]) -> PlanningSession:
        session = PlanningSession(
            id=session_id,
            user_profile_id=user_profile_id,
            status=SessionStatus.PENDING,
        )
        self.db.add(session)
        return session

    def get_by_id(self, session_id: str) -> Optional[PlanningSession]:
        return self.get(session_id)

    def list_recent(self, limit: int = 100):
        return (
            self.db.query(PlanningSession)
            .order_by(PlanningSession.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_cascade(self, session_id: str):
        """
        Delete a session and everything under it (POIs, itinerary days, chat,
        journal entries + media, and the profile if unused). Returns the list of
        media file paths that were attached, or None if the session is missing.
        Does not commit.
        """
        from ..models import (
            ChatMessage, ItineraryDay, JournalEntry, POI, UserProfile,
        )

        session = self.get(session_id)
        if not session:
            return None

        entries = (
            self.db.query(JournalEntry)
            .filter(JournalEntry.session_id == session_id)
            .all()
        )
        media_paths = [m.file_path for e in entries for m in e.media]
        for entry in entries:            # cascade removes its media rows
            self.db.delete(entry)

        for model in (POI, ItineraryDay, ChatMessage):
            self.db.query(model).filter(model.session_id == session_id).delete(
                synchronize_session=False
            )

        profile_id = session.user_profile_id
        self.db.delete(session)

        if profile_id:
            others = (
                self.db.query(PlanningSession)
                .filter(
                    PlanningSession.user_profile_id == profile_id,
                    PlanningSession.id != session_id,
                )
                .count()
            )
            if others == 0:
                profile = self.db.get(UserProfile, profile_id)
                if profile:
                    self.db.delete(profile)

        return media_paths

    def set_status(self, session: PlanningSession, status: str) -> None:
        session.status = status
        if status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
            session.completed_at = datetime.utcnow()

    def apply_stats(self, session: PlanningSession, stats: dict) -> None:
        session.total_pois_scraped = stats.get("total_scraped", session.total_pois_scraped)
        session.total_pois_verified = stats.get("total_verified", session.total_pois_verified)
        session.total_pois_included = stats.get("total_included", session.total_pois_included)
