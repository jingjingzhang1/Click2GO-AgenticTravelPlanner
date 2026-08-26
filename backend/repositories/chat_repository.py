"""DAO for Design-Agent chat history."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import ChatMessage
from .base import BaseRepository


class ChatRepository(BaseRepository[ChatMessage]):
    model = ChatMessage

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            metadata_=metadata,
        )
        self.db.add(msg)
        return msg

    def history(self, session_id: str) -> List[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
