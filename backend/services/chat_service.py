"""
Chat / design service
======================
Wraps the Design Agent (Agent 3) behind the repository + mapper layers.
Handles free-form chat customization and deterministic map-config toggles,
persisting chat history and tracking per-session map state.
"""
from __future__ import annotations

import os
from typing import Dict

from sqlalchemy.orm import Session

from ..agents.design_agent import DesignAgent
from ..mappers import profile_to_summary, session_to_itinerary_dict
from ..models import SessionStatus
from ..repositories import ChatRepository, POIRepository, ProfileRepository, SessionRepository
from ..schemas import ChatMessageResponse
from .exceptions import ConflictError, NotFoundError

_ALLOWED_MAP_CONFIG_KEYS = {"tile_layer", "show_routes", "show_distances"}

# Shared, stateless-per-request agent + in-memory per-session map config.
# (In production this would live in Redis; kept in-process for the demo.)
_design_agent = DesignAgent()
_session_map_configs: Dict[str, dict] = {}


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = SessionRepository(db)
        self.profiles = ProfileRepository(db)
        self.pois = POIRepository(db)
        self.chats = ChatRepository(db)

    def _require_session(self, session_id: str, require_completed: bool = True):
        session = self.sessions.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")
        if require_completed and session.status != SessionStatus.COMPLETED:
            raise ConflictError("Chat is only available after planning is complete.")
        return session

    def _context(self, session_id: str, session):
        profile = (self.profiles.get_by_id(session.user_profile_id)
                   if session.user_profile_id else None)
        summary = profile_to_summary(profile)
        grouped = self.pois.group_by_day(session_id)
        itinerary = session_to_itinerary_dict(
            session_id, grouped, persona_tags=summary["personas"]
        )
        return summary, itinerary

    # ── free-form chat ──────────────────────────────────────────────────
    def handle_message(self, session_id: str, message: str) -> ChatMessageResponse:
        session = self._require_session(session_id)
        summary, itinerary = self._context(session_id, session)

        history = [{"role": m.role, "content": m.content}
                   for m in self.chats.history(session_id)]
        self.chats.add_message(session_id, "user", message)
        self.db.commit()

        result = _design_agent.handle_chat(
            session_id=session_id,
            user_message=message,
            itinerary=itinerary,
            user_profile=summary,
            chat_history=history,
            current_map_config=_session_map_configs.get(session_id, {}),
        )

        if result.get("new_map_config"):
            _session_map_configs[session_id] = result["new_map_config"]

        self.chats.add_message(session_id, "assistant", result["response"])
        self.db.commit()

        return ChatMessageResponse(
            role="assistant",
            content=result["response"],
            map_updated=result.get("map_updated", False),
            pdf_updated=result.get("pdf_updated", False),
            map_url=result.get("map_url"),
            pdf_url=result.get("pdf_url"),
        )

    def history(self, session_id: str) -> Dict:
        self._require_session(session_id, require_completed=False)
        return {
            "session_id": session_id,
            "messages": [{"role": m.role, "content": m.content}
                         for m in self.chats.history(session_id)],
        }

    # ── deterministic map-config toggles (no LLM) ───────────────────────
    def update_map_config(self, session_id: str, raw_changes: dict) -> Dict:
        session = self._require_session(session_id)
        changes = {k: v for k, v in (raw_changes or {}).items()
                   if k in _ALLOWED_MAP_CONFIG_KEYS}
        if not changes:
            raise ConflictError("No valid map-config changes supplied.")

        summary, itinerary = self._context(session_id, session)
        new_config = {**_session_map_configs.get(session_id, {}), **changes}
        map_path = _design_agent._generate_styled_map(itinerary, summary, new_config)
        _session_map_configs[session_id] = new_config

        return {
            "map_url": f"/outputs/{os.path.basename(map_path)}",
            "map_config": new_config,
        }
