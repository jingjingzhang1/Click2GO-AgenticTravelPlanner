"""
Repository (DAO) layer
======================
Encapsulates **all** database access behind small, testable classes so the
service layer never issues raw ORM queries. Each repository owns one aggregate
and exposes intention-revealing methods (``get_fresh_for_destination``,
``upsert_many``…) instead of leaking SQLAlchemy query objects upward.

    router  →  service  →  repository  →  SQLAlchemy ORM  →  DB

Repositories are constructed with an active ``Session`` and never commit on
their own unless the method name says so (``*_committed``); transaction
boundaries belong to the service/unit-of-work layer.
"""
from .base import BaseRepository
from .chat_repository import ChatRepository
from .journal_repository import JournalRepository
from .poi_cache_repository import POICacheRepository
from .poi_repository import POIRepository
from .profile_repository import ProfileRepository
from .session_repository import SessionRepository

__all__ = [
    "BaseRepository",
    "ChatRepository",
    "JournalRepository",
    "POICacheRepository",
    "POIRepository",
    "ProfileRepository",
    "SessionRepository",
]
