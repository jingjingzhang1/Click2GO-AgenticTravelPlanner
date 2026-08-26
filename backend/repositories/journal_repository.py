"""DAO for the on-the-trip travel journal."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..models import JournalEntry, JournalMedia
from .base import BaseRepository


class JournalRepository(BaseRepository[JournalEntry]):
    model = JournalEntry

    def create_entry(
        self,
        *,
        session_id: str,
        spot_name: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        note: Optional[str] = None,
        transcript: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            session_id=session_id,
            spot_name=spot_name,
            lat=lat,
            lng=lng,
            note=note,
            transcript=transcript,
            rating=rating,
            visited_at=datetime.utcnow(),
        )
        self.db.add(entry)
        return entry

    def get_entry(self, entry_id: int) -> Optional[JournalEntry]:
        return self.get(entry_id)

    def count_for_session(self, session_id: str) -> int:
        return (
            self.db.query(JournalEntry)
            .filter(JournalEntry.session_id == session_id)
            .count()
        )

    def for_session(self, session_id: str) -> List[JournalEntry]:
        return (
            self.db.query(JournalEntry)
            .filter(JournalEntry.session_id == session_id)
            .order_by(JournalEntry.created_at)
            .all()
        )

    def add_media(
        self,
        entry_id: int,
        media_type: str,
        file_path: str,
        caption: Optional[str] = None,
    ) -> JournalMedia:
        media = JournalMedia(
            entry_id=entry_id,
            media_type=media_type,
            file_path=file_path,
            caption=caption,
        )
        self.db.add(media)
        return media
