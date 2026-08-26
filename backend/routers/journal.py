"""
Journal Router (thin controller)
================================
The on-the-trip travel journal.

    POST /api/v1/plan/{id}/journal            – add a memory (note / voice transcript)
    GET  /api/v1/plan/{id}/journal            – list memories
    POST /api/v1/journal/{entry_id}/media     – attach a photo or audio file
    GET  /api/v1/plan/{id}/travel-log         – roll up into a trip summary
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import JournalEntryRequest
from ..services.journal_service import JournalService

router = APIRouter()


@router.post("/plan/{session_id}/journal", status_code=201)
async def add_journal_entry(
    session_id: str,
    body: JournalEntryRequest,
    db: Session = Depends(get_db),
):
    """Save a memory for a spot (typed note and/or voice-note transcript)."""
    return JournalService(db).add_entry(session_id, body)


@router.get("/plan/{session_id}/journal")
async def list_journal(session_id: str, db: Session = Depends(get_db)):
    """List all journal entries for a trip."""
    return {"session_id": session_id, "entries": JournalService(db).list_entries(session_id)}


@router.post("/journal/{entry_id}/media", status_code=201)
async def upload_journal_media(
    entry_id: int,
    session_id: str = Form(...),
    caption: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Attach a photo or audio file to a journal entry."""
    content = await file.read()
    return JournalService(db).attach_media(
        session_id=session_id,
        entry_id=entry_id,
        content=content,
        content_type=file.content_type or "application/octet-stream",
        caption=caption,
    )


@router.get("/plan/{session_id}/travel-log")
async def travel_log(session_id: str, db: Session = Depends(get_db)):
    """Roll all memories up into a shareable trip summary."""
    return JournalService(db).travel_log(session_id)
