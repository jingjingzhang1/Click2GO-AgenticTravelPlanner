"""
Planning Router (thin controller)
=================================
Delegates all business logic to ``PlanningService``. Domain exceptions raised
by the service are translated to HTTP responses by the global handlers
registered in ``main.py``.

    POST /api/v1/plan                 – start a new planning session (async)
    GET  /api/v1/plan/{id}/status     – poll pipeline progress
    GET  /api/v1/plan/{id}/result     – retrieve the completed itinerary
"""
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SessionStatus
from ..schemas import PlanningRequest, PlanningSessionResponse, PlanningStatusResponse
from ..services.planning_service import PlanningService

router = APIRouter()


@router.post("/plan", response_model=PlanningSessionResponse, status_code=202)
async def create_plan(
    request: PlanningRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Start a new agentic travel-planning session.

    The multi-agent supervisor pipeline runs asynchronously. Poll
    **GET /api/v1/plan/{session_id}/status**, then
    **GET /api/v1/plan/{session_id}/result** for the final itinerary.
    """
    session_id, payload = PlanningService(db).create_plan(request)
    background_tasks.add_task(PlanningService.run_pipeline, session_id, payload)

    return PlanningSessionResponse(
        session_id=session_id,
        status=SessionStatus.PENDING,
        message=(
            f"Planning session started for {request.destination}. "
            f"Poll /api/v1/plan/{session_id}/status for updates."
        ),
    )


@router.get("/trips")
async def list_trips(db: Session = Depends(get_db)):
    """List every saved trip (most recent first) for the My-Trips browser."""
    return {"trips": PlanningService(db).list_trips()}


@router.get("/plan/{session_id}/status", response_model=PlanningStatusResponse)
async def get_plan_status(session_id: str, db: Session = Depends(get_db)):
    """Poll the progress of a planning session."""
    return PlanningService(db).get_status(session_id)


@router.get("/plan/{session_id}/result", response_model=PlanningSessionResponse)
async def get_plan_result(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the completed itinerary for a session."""
    return PlanningService(db).get_result(session_id)


@router.delete("/plan/{session_id}")
async def delete_plan(session_id: str, db: Session = Depends(get_db)):
    """Delete a trip and all of its data (itinerary, journal, files)."""
    return PlanningService(db).delete_trip(session_id)
