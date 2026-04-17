"""
Chat Router
===========
POST /api/v1/plan/{session_id}/chat  – send a message to the Design Agent
GET  /api/v1/plan/{session_id}/chat  – retrieve chat history
"""
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import POI, PlanningSession, SessionStatus, UserProfile
from ..schemas import ChatMessageRequest, ChatMessageResponse
from ..agents.design_agent import DesignAgent
from ..tools.db_tools import get_chat_history, save_chat_message

router = APIRouter()

# Shared design agent instance + per-session map configs
_design_agent = DesignAgent()
_session_map_configs: Dict[str, dict] = {}


def _load_itinerary(session_id: str, db: Session, personas: Optional[List[str]] = None) -> dict:
    """Load the itinerary data for a session from the database."""
    pois = (
        db.query(POI)
        .filter(POI.session_id == session_id, POI.day_number.isnot(None))
        .order_by(POI.day_number, POI.stop_order)
        .all()
    )

    # Use the user's personas as tags so highlighting works
    tags = personas or []

    days_map: Dict[int, List[dict]] = {}
    for poi in pois:
        dn = poi.day_number or 1
        days_map.setdefault(dn, []).append({
            "name": poi.name,
            "address": poi.address,
            "lat": poi.lat,
            "lng": poi.lng,
            "category": poi.category,
            "persona_score": poi.persona_score,
            "agent_note": poi.agent_note,
            "is_open": poi.is_open,
            "persona_tags": tags,
            "likes": poi.likes,
        })

    return {
        "session_id": session_id,
        "days": [days_map[dn] for dn in sorted(days_map.keys())],
        "stats": {},
    }


@router.post("/plan/{session_id}/chat", response_model=ChatMessageResponse)
async def chat_with_design_agent(
    session_id: str,
    body: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """
    Send a message to the Design Agent to customize your map or itinerary.

    Examples:
      - "Make the map dark mode"
      - "Highlight foodie spots"
      - "Hide the route lines"
      - "Generate a cover image"
      - "Switch to satellite view"
    """
    # Validate session
    session = db.query(PlanningSession).filter(
        PlanningSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")
    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Chat is only available after planning is complete.",
        )

    # Load profile and itinerary
    profile = db.query(UserProfile).filter(
        UserProfile.id == session.user_profile_id
    ).first()
    personas_list = (profile.personas.split(",") if profile and profile.personas
                     else ["chilling"])
    user_profile = {
        "destination": profile.destination if profile else "Unknown",
        "start_date": profile.start_date if profile else "",
        "end_date": profile.end_date if profile else "",
        "persona": profile.personas if profile else "chilling",
        "personas": personas_list,
    }

    itinerary = _load_itinerary(session_id, db, personas=personas_list)
    chat_history = get_chat_history(session_id)

    # Save user message
    save_chat_message(session_id, "user", body.message)

    # Get current map config for this session
    map_config = _session_map_configs.get(session_id, {})

    # Run the Design Agent
    result = _design_agent.handle_chat(
        session_id=session_id,
        user_message=body.message,
        itinerary=itinerary,
        user_profile=user_profile,
        chat_history=chat_history,
        current_map_config=map_config,
    )

    # Update stored map config
    if result.get("new_map_config"):
        _session_map_configs[session_id] = result["new_map_config"]

    # Save assistant response
    save_chat_message(session_id, "assistant", result["response"])

    return ChatMessageResponse(
        role="assistant",
        content=result["response"],
        map_updated=result.get("map_updated", False),
        pdf_updated=result.get("pdf_updated", False),
        map_url=result.get("map_url"),
        pdf_url=result.get("pdf_url"),
    )


@router.get("/plan/{session_id}/chat")
async def get_chat(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the chat history for a session."""
    session = db.query(PlanningSession).filter(
        PlanningSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")

    return {"session_id": session_id, "messages": get_chat_history(session_id)}


_ALLOWED_MAP_CONFIG_KEYS = {"tile_layer", "show_routes", "show_distances"}


@router.post("/plan/{session_id}/map-config")
async def update_map_config(
    session_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    """
    Apply deterministic UI-toggle changes to the map without invoking the LLM.
    Body: {"changes": {"show_distances": true, ...}}
    """
    session = db.query(PlanningSession).filter(
        PlanningSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Planning session not found")
    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Map is not ready yet.")

    raw_changes = (body or {}).get("changes") or {}
    changes = {k: v for k, v in raw_changes.items() if k in _ALLOWED_MAP_CONFIG_KEYS}
    if not changes:
        raise HTTPException(status_code=400, detail="No valid map-config changes supplied.")

    profile = db.query(UserProfile).filter(
        UserProfile.id == session.user_profile_id
    ).first()
    personas_list = (profile.personas.split(",") if profile and profile.personas
                     else ["chilling"])
    user_profile = {
        "destination": profile.destination if profile else "Unknown",
        "start_date": profile.start_date if profile else "",
        "end_date": profile.end_date if profile else "",
        "persona": profile.personas if profile else "chilling",
        "personas": personas_list,
    }
    itinerary = _load_itinerary(session_id, db, personas=personas_list)

    current = _session_map_configs.get(session_id, {})
    new_config = {**current, **changes}
    map_path = _design_agent._generate_styled_map(itinerary, user_profile, new_config)
    _session_map_configs[session_id] = new_config

    return {
        "map_url": f"/outputs/{os.path.basename(map_path)}",
        "map_config": new_config,
    }
