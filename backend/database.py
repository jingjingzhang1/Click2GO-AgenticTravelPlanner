import logging
import os
import shutil

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# ── Seed database paths ─────────────────────────────────────────────────────
# seed_database.sqlite = master file tracked in Git (pre-scraped POIs)
# click2go.db          = user's local copy (gitignored)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED_DB_PATH = os.path.join(_PROJECT_ROOT, "seed_database.sqlite")
LOCAL_DB_PATH = os.path.join(_PROJECT_ROOT, "click2go.db")

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _init_from_seed():
    """
    Seed Database Strategy:
      1. If click2go.db doesn't exist and seed_database.sqlite does,
         copy the seed to create the user's local database.
      2. If both exist but the seed is newer, merge new POIs from the
         seed into click2go.db without touching the user's itineraries.
    """
    if not os.path.exists(SEED_DB_PATH):
        return

    if not os.path.exists(LOCAL_DB_PATH):
        logger.info("First run — copying seed database to click2go.db")
        shutil.copy2(SEED_DB_PATH, LOCAL_DB_PATH)
        return

    # Check if the seed has been updated (e.g. after git pull)
    seed_mtime = os.path.getmtime(SEED_DB_PATH)
    local_mtime = os.path.getmtime(LOCAL_DB_PATH)

    if seed_mtime <= local_mtime:
        return

    logger.info("Seed database updated — merging new POIs into click2go.db")
    _merge_seed_pois()


def _merge_seed_pois():
    """
    Merge POIs from the seed database into the user's local database.
    Only affects the poi_cache table — never touches planning_sessions,
    pois (user itineraries), chat_messages, or user_profiles.
    """
    from sqlalchemy import create_engine as _ce

    seed_engine = _ce(f"sqlite:///{SEED_DB_PATH}", connect_args={"check_same_thread": False})

    try:
        with seed_engine.connect() as seed_conn:
            # Check if the seed has a poi_cache table
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

                # Check if this POI already exists locally
                existing = local_conn.execute(
                    text("SELECT id FROM poi_cache WHERE destination = :dest AND name = :name"),
                    {"dest": dest, "name": name},
                ).fetchone()

                if not existing:
                    # Insert new POI from seed
                    cols = ", ".join(c for c in col_names if c != "id")
                    placeholders = ", ".join(f":{c}" for c in col_names if c != "id")
                    params = {c: row_dict[c] for c in col_names if c != "id"}
                    local_conn.execute(
                        text(f"INSERT INTO poi_cache ({cols}) VALUES ({placeholders})"),
                        params,
                    )

            local_conn.commit()

        logger.info("Seed merge complete — %d POIs checked", len(seed_rows))

    except Exception as e:
        logger.warning("Seed merge failed (non-fatal): %s", e)
    finally:
        seed_engine.dispose()


def create_tables():
    """Create all tables on startup, then apply seed data if available."""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _init_from_seed()
