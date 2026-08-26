"""
Journal service
===============
The on-the-trip companion: travellers tap a spot on their map and attach
memories — a typed note, a voice-note transcript, photos, and audio — all
saved to their own database. ``travel_log`` rolls the entries up into a
shareable trip summary.

Media files are written to ``media/`` and served under ``/media``; the DB keeps
only the reference (path), which keeps rows small and the files cacheable.
"""
from __future__ import annotations

import os
import uuid
from typing import Dict, List

from sqlalchemy.orm import Session

from ..observability import get_logger
from ..repositories import JournalRepository, ProfileRepository, SessionRepository
from ..schemas import JournalEntryRequest
from .exceptions import NotFoundError

logger = get_logger("click2go.journal")

MEDIA_DIR = "media"
_PHOTO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic"}
_AUDIO_EXT = {"audio/webm": "webm", "audio/mpeg": "mp3", "audio/mp4": "m4a",
              "audio/wav": "wav", "audio/ogg": "ogg"}


class JournalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.journal = JournalRepository(db)
        self.sessions = SessionRepository(db)
        self.profiles = ProfileRepository(db)

    def _require_session(self, session_id: str):
        session = self.sessions.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")
        return session

    # ── entries ─────────────────────────────────────────────────────────
    def add_entry(self, session_id: str, body: JournalEntryRequest) -> Dict:
        self._require_session(session_id)
        entry = self.journal.create_entry(
            session_id=session_id,
            spot_name=body.spot_name,
            lat=body.lat,
            lng=body.lng,
            note=body.note,
            transcript=body.transcript,
            rating=body.rating,
        )
        self.db.commit()
        self.db.refresh(entry)
        logger.info("journal entry added", extra={"session_id": session_id, "spot": body.spot_name})
        return self._entry_dict(entry)

    def list_entries(self, session_id: str) -> List[Dict]:
        self._require_session(session_id)
        return [self._entry_dict(e) for e in self.journal.for_session(session_id)]

    # ── media ───────────────────────────────────────────────────────────
    def attach_media(
        self,
        session_id: str,
        entry_id: int,
        content: bytes,
        content_type: str,
        caption: str | None = None,
    ) -> Dict:
        self._require_session(session_id)
        entry = self.journal.get_entry(entry_id)
        if not entry or entry.session_id != session_id:
            raise NotFoundError("Journal entry not found")

        media_type = "audio" if content_type.startswith("audio") else "photo"
        ext = (_AUDIO_EXT if media_type == "audio" else _PHOTO_EXT).get(content_type, "bin")
        os.makedirs(MEDIA_DIR, exist_ok=True)
        filename = f"{session_id[:8]}_{entry_id}_{uuid.uuid4().hex[:8]}.{ext}"
        with open(os.path.join(MEDIA_DIR, filename), "wb") as f:
            f.write(content)

        media = self.journal.add_media(entry_id, media_type, f"/media/{filename}", caption)
        self.db.commit()
        self.db.refresh(media)
        return {"id": media.id, "media_type": media.media_type,
                "url": media.file_path, "caption": media.caption}

    # ── summary ─────────────────────────────────────────────────────────
    def travel_log(self, session_id: str) -> Dict:
        session = self._require_session(session_id)
        profile = (self.profiles.get_by_id(session.user_profile_id)
                   if session.user_profile_id else None)
        entries = [self._entry_dict(e) for e in self.journal.for_session(session_id)]
        photos = sum(1 for e in entries for m in e["media"] if m["media_type"] == "photo")
        voices = sum(1 for e in entries for m in e["media"] if m["media_type"] == "audio")
        return {
            "session_id": session_id,
            "destination": profile.destination if profile else None,
            "hotel": profile.hotel_name if profile else None,
            "entry_count": len(entries),
            "photo_count": photos,
            "voice_count": voices,
            "entries": entries,
        }

    # ── mapping ─────────────────────────────────────────────────────────
    @staticmethod
    def _entry_dict(entry) -> Dict:
        return {
            "id": entry.id,
            "session_id": entry.session_id,
            "spot_name": entry.spot_name,
            "lat": entry.lat,
            "lng": entry.lng,
            "note": entry.note,
            "transcript": entry.transcript,
            "rating": entry.rating,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "media": [
                {"id": m.id, "media_type": m.media_type, "url": m.file_path, "caption": m.caption}
                for m in entry.media
            ],
        }
