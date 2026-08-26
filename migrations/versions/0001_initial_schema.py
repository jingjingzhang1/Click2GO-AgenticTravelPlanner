"""initial schema — user_profiles, planning_sessions, pois, itinerary_days, poi_cache, chat_messages

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("destination", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.String(length=20)),
        sa.Column("end_date", sa.String(length=20)),
        sa.Column("personas", sa.String(length=200)),
        sa.Column("allergies", sa.JSON()),
        sa.Column("budget", sa.String(length=50)),
        sa.Column("language", sa.String(length=10)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_user_profiles_id", "user_profiles", ["id"])

    op.create_table(
        "planning_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_profile_id", sa.Integer(), sa.ForeignKey("user_profiles.id")),
        sa.Column("status", sa.String(length=50)),
        sa.Column("total_pois_scraped", sa.Integer()),
        sa.Column("total_pois_verified", sa.Integer()),
        sa.Column("total_pois_included", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime()),
    )

    op.create_table(
        "pois",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("planning_sessions.id")),
        sa.Column("name", sa.String(length=500)),
        sa.Column("address", sa.String(length=1000)),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("category", sa.String(length=100)),
        sa.Column("likes", sa.Integer()),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("raw_content", sa.Text()),
        sa.Column("is_verified", sa.Boolean()),
        sa.Column("is_open", sa.Boolean()),
        sa.Column("seasonal_match", sa.Boolean()),
        sa.Column("persona_score", sa.Float()),
        sa.Column("verification_recommendation", sa.String(length=10)),
        sa.Column("agent_note", sa.Text()),
        sa.Column("day_number", sa.Integer()),
        sa.Column("stop_order", sa.Integer()),
    )
    op.create_index("ix_pois_id", "pois", ["id"])
    op.create_index("ix_pois_session_id", "pois", ["session_id"])

    op.create_table(
        "itinerary_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("planning_sessions.id")),
        sa.Column("day_number", sa.Integer()),
        sa.Column("date", sa.String(length=20)),
        sa.Column("poi_sequence", sa.JSON()),
        sa.Column("cluster_center_lat", sa.Float()),
        sa.Column("cluster_center_lng", sa.Float()),
    )
    op.create_index("ix_itinerary_days_id", "itinerary_days", ["id"])

    op.create_table(
        "poi_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("destination", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("address", sa.String(length=1000)),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("category", sa.String(length=100)),
        sa.Column("persona_tags", sa.JSON()),
        sa.Column("persona_score", sa.Float()),
        sa.Column("is_open", sa.Boolean()),
        sa.Column("seasonal_info", sa.Text()),
        sa.Column("agent_note", sa.Text()),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("raw_content", sa.Text()),
        sa.Column("likes", sa.Integer()),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("verified_at", sa.DateTime()),
    )
    op.create_index("ix_poi_cache_id", "poi_cache", ["id"])
    op.create_index("ix_poi_cache_destination", "poi_cache", ["destination"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("planning_sessions.id")),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_id", "chat_messages", ["id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("poi_cache")
    op.drop_table("itinerary_days")
    op.drop_table("pois")
    op.drop_table("planning_sessions")
    op.drop_table("user_profiles")
