"""hotel + reservation fields, and the travel-journal tables

Revision ID: 0002_journal
Revises: 0001_initial
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_journal"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Hotel fields on the profile ──────────────────────────────────────
    op.add_column("user_profiles", sa.Column("hotel_name", sa.String(length=300)))
    op.add_column("user_profiles", sa.Column("hotel_address", sa.String(length=1000)))
    op.add_column("user_profiles", sa.Column("hotel_lat", sa.Float()))
    op.add_column("user_profiles", sa.Column("hotel_lng", sa.Float()))

    # ── Reservation / practical info on places ───────────────────────────
    for table in ("pois", "poi_cache"):
        op.add_column(table, sa.Column("website", sa.String(length=500)))
        op.add_column(table, sa.Column("reservation_url", sa.String(length=500)))
        op.add_column(table, sa.Column("needs_reservation", sa.Boolean(), server_default=sa.false()))
    op.add_column("pois", sa.Column("transit_note", sa.String(length=500)))

    # ── Journal tables ───────────────────────────────────────────────────
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("planning_sessions.id")),
        sa.Column("spot_name", sa.String(length=500), nullable=False),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("note", sa.Text()),
        sa.Column("transcript", sa.Text()),
        sa.Column("rating", sa.Integer()),
        sa.Column("visited_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_journal_entries_id", "journal_entries", ["id"])
    op.create_index("ix_journal_entries_session_id", "journal_entries", ["session_id"])

    op.create_table(
        "journal_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id")),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("caption", sa.String(length=1000)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_journal_media_id", "journal_media", ["id"])
    op.create_index("ix_journal_media_entry_id", "journal_media", ["entry_id"])


def downgrade() -> None:
    op.drop_table("journal_media")
    op.drop_table("journal_entries")
    op.drop_column("pois", "transit_note")
    for table in ("pois", "poi_cache"):
        op.drop_column(table, "needs_reservation")
        op.drop_column(table, "reservation_url")
        op.drop_column(table, "website")
    for col in ("hotel_lng", "hotel_lat", "hotel_address", "hotel_name"):
        op.drop_column("user_profiles", col)
