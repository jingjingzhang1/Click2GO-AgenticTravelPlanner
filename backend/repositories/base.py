"""Generic base repository with common CRUD helpers."""
from __future__ import annotations

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from ..database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Thin generic DAO parameterised by an ORM model.

    Subclasses set ``model`` and add query methods expressed in domain terms.
    Kept intentionally small: repositories describe *what* to fetch/persist,
    services decide *when* to commit.
    """

    model: Type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, pk) -> Optional[ModelT]:
        return self.db.get(self.model, pk)

    def list(self, limit: int = 100) -> List[ModelT]:
        return self.db.query(self.model).limit(limit).all()

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)

    def flush(self) -> None:
        """Assign primary keys without ending the transaction."""
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
