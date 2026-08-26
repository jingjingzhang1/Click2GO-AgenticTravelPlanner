"""
Planning service
================
Orchestrates the planning use-cases (create → poll → fetch result) on top of
the repository + mapper layers. Contains **no** SQLAlchemy queries and **no**
FastAPI types — it is a pure application service.

The long-running multi-agent pipeline runs in a background worker
(``run_pipeline``) that opens its own unit-of-work, mirroring how a Celery/RQ
task would be structured in production.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..mappers import orm_to_itinerary_days
from ..models import SessionStatus
from ..observability import get_logger
from ..repositories import POIRepository, ProfileRepository, SessionRepository
from ..schemas import PlanningRequest, PlanningSessionResponse, PlanningStatusResponse
from .exceptions import InProgressError, NotFoundError

logger = get_logger("click2go.planning")

OUTPUTS_DIR = "outputs"

_STATUS_MESSAGES = {
    "pending": "Initialising planning session...",
    "scraping": "Agent 1 (Knowledge Manager): Discovering POIs from Xiaohongshu...",
    "verifying": "Agent 1 (Knowledge Manager): Running AI verification...",
    "routing": "Agent 2 (Route Optimizer): Clustering routes with K-Means...",
    "exporting": "Agent 3 (Design Agent): Generating map and PDF...",
    "completed": "Your itinerary is ready! Chat with the Design Agent to customize.",
    "failed": "Planning failed.",
}


class PlanningService:
    """Application service for the travel-planning workflow."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.sessions = SessionRepository(db)
        self.pois = POIRepository(db)

    # ── Use case: start a planning session ──────────────────────────────
    def create_plan(self, request: PlanningRequest) -> Tuple[str, Dict]:
        """
        Persist the profile + session and return the request payload the
        background worker needs. The caller schedules ``run_pipeline``.
        """
        personas_str = ",".join(p.value for p in request.personas)
        hotel = self._resolve_hotel(request)
        profile = self.profiles.create(
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            personas=personas_str,
            allergies=request.constraints.allergies,
            budget=request.constraints.budget,
            language=request.language,
            hotel=hotel,
        )
        self.db.flush()  # assign profile.id

        session_id = str(uuid.uuid4())
        self.sessions.create(session_id, profile.id)
        self.db.commit()

        payload = {
            "destination": request.destination,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "personas": [p.value for p in request.personas],
            "constraints": request.constraints.model_dump(),
            "hotel": hotel,
            "max_pois_per_day": request.max_pois_per_day,
            "language": request.language,
        }
        logger.info("planning session created", extra={"session_id": session_id,
                                                       "destination": request.destination})
        return session_id, payload

    @staticmethod
    def _resolve_hotel(request: PlanningRequest) -> dict:
        """Normalise + geocode the hotel so routing can anchor to it."""
        if not request.hotel:
            return {}
        hotel = request.hotel.model_dump()
        if hotel.get("address") and hotel.get("lat") is None:
            from ..tools.map_tool import MapTool
            coords = MapTool().geocode(hotel["address"])
            if coords:
                hotel["lat"], hotel["lng"] = coords
        return hotel

    # ── Use case: list all saved trips ──────────────────────────────────
    def list_trips(self) -> list:
        """Every saved trip (most recent first) with a memory count."""
        from ..repositories import JournalRepository
        journal = JournalRepository(self.db)
        trips = []
        for s in self.sessions.list_recent():
            profile = (self.profiles.get_by_id(s.user_profile_id)
                       if s.user_profile_id else None)
            trips.append({
                "session_id": s.id,
                "destination": profile.destination if profile else "Trip",
                "start_date": profile.start_date if profile else None,
                "end_date": profile.end_date if profile else None,
                "hotel": profile.hotel_name if profile else None,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "memory_count": journal.count_for_session(s.id),
            })
        return trips

    # ── Use case: delete a trip ─────────────────────────────────────────
    def delete_trip(self, session_id: str) -> dict:
        """Delete a trip and all of its data + generated files."""
        media_paths = self.sessions.delete_cascade(session_id)
        if media_paths is None:
            raise NotFoundError("Trip not found")
        self.db.commit()
        self._cleanup_files(session_id, media_paths)
        logger.info("trip deleted", extra={"session_id": session_id})
        return {"deleted": session_id}

    @staticmethod
    def _cleanup_files(session_id: str, media_paths: list) -> None:
        short = session_id[:8]
        candidates = [
            f"{OUTPUTS_DIR}/map_{short}.html",
            f"{OUTPUTS_DIR}/itinerary_{short}.pdf",
            f"{OUTPUTS_DIR}/poster_{short}_en.jpg",
            f"{OUTPUTS_DIR}/poster_{short}_zh.jpg",
        ]
        candidates += [p.lstrip("/") for p in media_paths]   # /media/x → media/x
        for path in candidates:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    # ── Use case: poll status ───────────────────────────────────────────
    def get_status(self, session_id: str) -> PlanningStatusResponse:
        session = self.sessions.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")

        message = _STATUS_MESSAGES.get(session.status, "Processing...")
        if session.status == SessionStatus.FAILED:
            message = f"Planning failed: {session.error_message or 'unknown error'}"

        return PlanningStatusResponse(
            session_id=session_id,
            status=session.status,
            progress_message=message,
            total_pois_scraped=session.total_pois_scraped,
            total_pois_verified=session.total_pois_verified,
            total_pois_included=session.total_pois_included,
            error_message=session.error_message,
        )

    # ── Use case: fetch the completed itinerary ─────────────────────────
    def get_result(self, session_id: str) -> PlanningSessionResponse:
        session = self.sessions.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")

        if session.status not in (SessionStatus.COMPLETED, SessionStatus.FAILED):
            raise InProgressError(session.status)

        grouped = self.pois.group_by_day(session_id)
        itinerary_days = orm_to_itinerary_days(grouped)

        profile = (self.profiles.get_by_id(session.user_profile_id)
                   if session.user_profile_id else None)
        hotel = None
        if profile and (profile.hotel_name or profile.hotel_lat):
            hotel = {"name": profile.hotel_name, "address": profile.hotel_address,
                     "lat": profile.hotel_lat, "lng": profile.hotel_lng}

        short = session_id[:8]
        pdf_url = f"/outputs/itinerary_{short}.pdf" \
            if os.path.exists(f"{OUTPUTS_DIR}/itinerary_{short}.pdf") else None
        map_url = f"/outputs/map_{short}.html" \
            if os.path.exists(f"{OUTPUTS_DIR}/map_{short}.html") else None

        return PlanningSessionResponse(
            session_id=session_id,
            status=session.status,
            message=("Itinerary generated successfully"
                     if session.status == SessionStatus.COMPLETED else "Session failed"),
            itinerary=itinerary_days,
            hotel=hotel,
            pdf_url=pdf_url,
            map_url=map_url,
            stats={
                "total_scraped": session.total_pois_scraped,
                "total_verified": session.total_pois_verified,
                "total_included": session.total_pois_included,
            },
        )

    # ── Background worker ───────────────────────────────────────────────
    @staticmethod
    def run_pipeline(session_id: str, request_data: dict) -> None:
        """
        Execute the multi-agent supervisor pipeline in its own DB session.
        Kept import-light at module load: heavy agent deps are imported lazily.
        """
        from ..agents.supervisor import MultiAgentSupervisor

        db = SessionLocal()
        sessions = SessionRepository(db)
        try:
            session = sessions.get_by_id(session_id)
            if not session:
                return

            sessions.set_status(session, SessionStatus.SCRAPING)
            db.commit()

            supervisor = MultiAgentSupervisor()
            result = supervisor.run({**request_data, "session_id": session_id})

            stats = result.get("stats", {})
            final = (SessionStatus.COMPLETED
                     if result.get("status") == "completed" else SessionStatus.FAILED)
            sessions.apply_stats(session, stats)
            session.error_message = result.get("error")
            sessions.set_status(session, final)
            session.completed_at = datetime.utcnow()
            db.commit()

            if final == SessionStatus.COMPLETED and settings.auto_generate_poster:
                PlanningService._safe_generate_poster(db, session_id, request_data)

            logger.info("pipeline finished", extra={"session_id": session_id, "status": final})

        except Exception as exc:  # noqa: BLE001 — worker must record failure, not crash
            db.rollback()
            sess = sessions.get_by_id(session_id)
            if sess:
                sess.status = SessionStatus.FAILED
                sess.error_message = str(exc)
                db.commit()
            logger.exception("pipeline crashed", extra={"session_id": session_id})
        finally:
            db.close()

    @staticmethod
    def _safe_generate_poster(db: Session, session_id: str, request_data: dict) -> None:
        """Best-effort final step: render the Gemini travel poster."""
        try:
            from .image_service import ImageService
            ImageService(db).generate_poster(session_id, request_data.get("language", "en"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto poster generation skipped: %s", exc)
