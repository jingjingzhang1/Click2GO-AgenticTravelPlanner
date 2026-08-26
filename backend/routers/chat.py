"""
Chat Router (thin controller)
=============================
POST /api/v1/plan/{session_id}/chat        – message the Design Agent (LLM)
GET  /api/v1/plan/{session_id}/chat        – retrieve chat history
POST /api/v1/plan/{session_id}/map-config  – deterministic UI toggles (no LLM)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ChatMessageRequest, ChatMessageResponse
from ..services.chat_service import ChatService

router = APIRouter()


@router.post("/plan/{session_id}/chat", response_model=ChatMessageResponse)
async def chat_with_design_agent(
    session_id: str,
    body: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """
    Send a message to the Design Agent to customize your map or itinerary.

    Examples: "Make the map dark mode", "Hide the route lines",
    "Show distances between stops", "Switch to satellite view".
    """
    return ChatService(db).handle_message(session_id, body.message)


@router.get("/plan/{session_id}/chat")
async def get_chat(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the chat history for a session."""
    return ChatService(db).history(session_id)


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
    return ChatService(db).update_map_config(session_id, (body or {}).get("changes") or {})
