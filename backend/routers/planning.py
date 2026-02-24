"""
Planning Router
===============
POST /api/v1/plan                    – start a new planning session (async)
GET  /api/v1/plan/{id}/status        – poll pipeline progress
GET  /api/v1/plan/{id}/result        – retrieve the completed itinerary
"""
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import ItineraryDay, POI, PlanningSession, SessionStatus, UserProfile
from ..schemas import (
    ItineraryDaySchema,
    POISchema,
    PlanningRequest,
    PlanningSessionResponse,
    PlanningStatusResponse,
)

router = APIRouter()


# ── Background task ───────────────────────────────────────────────────────────

def _run_pipeline(session_id: str, request_data: dict) -> None:
    """
    Runs the full Click2GO planning pipeline in a background thread.
    Opens its own DB session so FastAPI's request session isn't shared.
    """
    from ..agents.orchestrator import TravelPlanningOrchestrator

    db = SessionLocal()
    try:
        session = db.query(PlanningSession).filter(PlanningSession.id == session_id).first()
        if not session:
            return

        session.status = SessionStatus.SCRAPING
        db.commit()

        orchestrator = TravelPlanningOrchestrator()
        result       = orchestrator.run({**request_data, "session_id": session_id})

        # ── Persist POIs ──────────────────────────────────────────────────────
        session.status = SessionStatus.ROUTING
        db.commit()

        for day_idx, day_pois in enumerate(result.get("clustered_days", [])):
            for stop_idx, p in enumerate(day_pois):
                db.add(POI(
                    session_id   = session_id,
                    name         = p.get("name", ""),
                    address      = p.get("address"),
                    lat          = p.get("lat"),
                    lng          = p.get("lng"),
                    category     = p.get("category"),
                    likes        = p.get("likes", 0),
                    source_url   = p.get("source_url", ""),
                    raw_content  = (p.get("raw_content") or "")[:2000],
                    is_verified  = True,
                    is_open      = p.get("is_open"),
                    seasonal_match = p.get("seasonal_match"),
                    persona_score  = p.get("persona_score"),
                    verification_recommendation = p.get("recommendation"),
                    agent_note   = p.get("agent_note", ""),
                    day_number   = day_idx + 1,
                    stop_order   = stop_idx + 1,
                ))

        for day_idx, day_pois in enumerate(result.get("clustered_days", [])):
            db.add(ItineraryDay(
                session_id   = session_id,
                day_number   = day_idx + 1,
                poi_sequence = [p.get("name") for p in day_pois],
            ))

        # ── Update session stats ──────────────────────────────────────────────
        stats = result.get("stats", {})
        session.status              = (
            SessionStatus.COMPLETED if result.get("status") == "completed"
            else SessionStatus.FAILED
        )
        session.total_pois_scraped  = stats.get("total_scraped", 0)
        session.total_pois_verified = stats.get("total_verified", 0)
        session.total_pois_included = stats.get("total_included", 0)
        session.completed_at        = datetime.utcnow()
        session.error_message       = result.get("error")
        db.commit()

    except Exception as exc:
        db.rollback()
        sess = db.query(PlanningSession).filter(PlanningSession.id == session_id).first()
        if sess:
            sess.status        = SessionStatus.FAILED
            sess.error_message = str(exc)
            db.commit()
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/plan", response_model=PlanningSessionResponse, status_code=202)
async def create_plan(
    request: PlanningRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Start a new agentic travel planning session.

    The pipeline runs asynchronously.
    Poll **GET /api/v1/plan/{session_id}/status** to track progress,
    then **GET /api/v1/plan/{session_id}/result** for the final itinerary.
    """
    personas_str = ",".join(p.value for p in request.personas)
    profile = UserProfile(
        destination = request.destination,
        start_date  = request.start_date,
        end_date    = request.end_date,
        persona     = personas_str,
        allergies   = request.constraints.allergies,
        budget      = request.constraints.budget,
        language    = request.language,
    )
    db.add(profile)
    db.flush()

    session_id = str(uuid.uuid4())
    session    = PlanningSession(
        id              = session_id,
        user_profile_id = profile.id,
        status          = SessionStatus.PENDING,
    )
    db.add(session)
    db.commit()

    background_tasks.add_task(
        _run_pipeline,
        session_id,
        {
            "destination":      request.destination,
            "start_date":       request.start_date,
            "end_date":         request.end_date,
            "personas":         [p.value for p in request.personas],
            "constraints":      request.constraints.model_dump(),
            "max_pois_per_day": request.max_pois_per_day,
        },
    )

    return PlanningSessionResponse(
        session_id = session_id,
        status     = SessionStatus.PENDING,
        message    = (
            f"Planning session started for {request.destination}. "
            f"Poll /api/v1/plan/{session_id}/status for updates."
        ),
    )


@router.get("/plan/{session_id}/status", response_model=PlanningStatusResponse)
async def get_plan_status(session_id: str, db: Session = Depends(get_db)):
    """Poll the progress of a planning session."""
    session = db.query(PlanningSession).filter(PlanningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")

    messages = {
        "pending":   "Initialising planning session…",
        "scraping":  "Discovering Points of Interest from Xiaohongshu…",
        "verifying": "Running Agentic Verification on each location…",
        "routing":   "Optimising daily routes with K-Means clustering…",
        "exporting": "Generating PDF and interactive map…",
        "completed": "Your itinerary is ready!",
        "failed":    f"Planning failed: {session.error_message or 'unknown error'}",
    }

    return PlanningStatusResponse(
        session_id          = session_id,
        status              = session.status,
        progress_message    = messages.get(session.status, "Processing…"),
        total_pois_scraped  = session.total_pois_scraped,
        total_pois_verified = session.total_pois_verified,
        total_pois_included = session.total_pois_included,
        error_message       = session.error_message,
    )


@router.get("/plan/{session_id}/result", response_model=PlanningSessionResponse)
async def get_plan_result(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the completed itinerary for a session."""
    session = db.query(PlanningSession).filter(PlanningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")

    if session.status not in (SessionStatus.COMPLETED, SessionStatus.FAILED):
        raise HTTPException(
            status_code=202,
            detail=f"Session still in progress: {session.status}",
        )

    pois = (
        db.query(POI)
        .filter(POI.session_id == session_id, POI.day_number.isnot(None))
        .order_by(POI.day_number, POI.stop_order)
        .all()
    )

    days_map: dict = {}
    for poi in pois:
        dn = poi.day_number or 1
        days_map.setdefault(dn, []).append(POISchema.model_validate(poi))

    itinerary_days = [
        ItineraryDaySchema(day_number=dn, pois=ps)
        for dn, ps in sorted(days_map.items())
    ]

    pdf_url = map_url = None
    if os.path.exists(f"outputs/itinerary_{session_id[:8]}.pdf"):
        pdf_url = f"/outputs/itinerary_{session_id[:8]}.pdf"
    if os.path.exists(f"outputs/map_{session_id[:8]}.html"):
        map_url = f"/outputs/map_{session_id[:8]}.html"

    return PlanningSessionResponse(
        session_id = session_id,
        status     = session.status,
        message    = (
            "Itinerary generated successfully"
            if session.status == SessionStatus.COMPLETED
            else "Session failed"
        ),
        itinerary = itinerary_days,
        pdf_url   = pdf_url,
        map_url   = map_url,
        stats     = {
            "total_scraped":  session.total_pois_scraped,
            "total_verified": session.total_pois_verified,
            "total_included": session.total_pois_included,
        },
    )
