"""
Database engine & session management
====================================
Supports two deployment modes from a single ``DATABASE_URL``:

* **SQLite** (default) — zero-config, file-based. Ships a Git-tracked
  ``seed_database.sqlite`` that is copied to a local ``click2go.db`` on first
  run so forks start with pre-scraped POIs.
* **PostgreSQL** (opt-in) — set ``DATABASE_URL`` to a Postgres DSN and the
  app uses a pooled connection so each fork can host its own planning
  database. Schema is managed by Alembic migrations (``alembic upgrade head``).

The seed-copy strategy only applies to SQLite; Postgres deployments are
provisioned via migrations instead.
"""
from __future__ import annotations

import logging
import os
import shutil

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# ── Seed database paths (SQLite only) ────────────────────────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED_DB_PATH = os.path.join(_PROJECT_ROOT, "seed_database.sqlite")
LOCAL_DB_PATH = os.path.join(_PROJECT_ROOT, "click2go.db")


def _build_engine():
    """Create a SQLAlchemy engine tuned for the configured backend."""
    if settings.is_sqlite:
        return create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.db_echo,
            connect_args={"check_same_thread": False},
        )

    # Pooled engine for Postgres / other server-based backends.
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
        echo=settings.db_echo,
    )


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Seed strategy (SQLite) ───────────────────────────────────────────────────

def _init_from_seed() -> None:
    """
    Seed strategy (SQLite only):
      1. If click2go.db doesn't exist and seed_database.sqlite does,
         copy the seed to create the user's local database.
      2. If both exist but the seed is newer (e.g. after ``git pull``),
         merge new POIs from the seed into poi_cache without touching the
         user's itineraries or session data.
    """
    if not settings.is_sqlite or not os.path.exists(SEED_DB_PATH):
        return

    if not os.path.exists(LOCAL_DB_PATH):
        logger.info("First run — copying seed database to click2go.db")
        shutil.copy2(SEED_DB_PATH, LOCAL_DB_PATH)
        return

    if os.path.getmtime(SEED_DB_PATH) <= os.path.getmtime(LOCAL_DB_PATH):
        return

    logger.info("Seed database updated — merging new POIs into click2go.db")
    _merge_seed_pois()


def _merge_seed_pois() -> None:
    """
    Merge POIs from the seed database into the user's local database.
    Only affects the ``poi_cache`` table — never touches planning_sessions,
    pois (user itineraries), chat_messages, or user_profiles.
    """
    from sqlalchemy import create_engine as _ce

    seed_engine = _ce(
        f"sqlite:///{SEED_DB_PATH}",
        connect_args={"check_same_thread": False},
    )

    try:
        with seed_engine.connect() as seed_conn:
            tables = seed_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='poi_cache'")
            ).fetchall()
            if not tables:
                return

            seed_rows = seed_conn.execute(text("SELECT * FROM poi_cache")).fetchall()
            seed_columns = seed_conn.execute(text("PRAGMA table_info(poi_cache)")).fetchall()
            col_names = [col[1] for col in seed_columns]

        if not seed_rows:
            return

        with engine.connect() as local_conn:
            for row in seed_rows:
                row_dict = dict(zip(col_names, row))
                name = row_dict.get("name", "")
                dest = row_dict.get("destination", "")

                existing = local_conn.execute(
                    text("SELECT id FROM poi_cache WHERE destination = :dest AND name = :name"),
                    {"dest": dest, "name": name},
                ).fetchone()

                if not existing:
                    cols = ", ".join(c for c in col_names if c != "id")
                    placeholders = ", ".join(f":{c}" for c in col_names if c != "id")
                    params = {c: row_dict[c] for c in col_names if c != "id"}
                    local_conn.execute(
                        text(f"INSERT INTO poi_cache ({cols}) VALUES ({placeholders})"),
                        params,
                    )

            local_conn.commit()

        logger.info("Seed merge complete — %d POIs checked", len(seed_rows))

    except Exception as e:  # noqa: BLE001 — seed merge must never crash startup
        logger.warning("Seed merge failed (non-fatal): %s", e)
    finally:
        seed_engine.dispose()


def create_tables() -> None:
    """
    Create all tables on startup, then apply seed data if available.

    For Postgres, prefer ``alembic upgrade head``; ``create_all`` remains a
    safe no-op when the schema already exists and keeps the test-suite and
    SQLite quick-start zero-config.
    """
    from . import models  # noqa: F401 — register models on the metadata
    Base.metadata.create_all(bind=engine)
    _init_from_seed()
