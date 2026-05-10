"""create events table

Revision ID: 0001_create_events
Revises:
Create Date: 2026-05-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("topic_category", sa.Text(), nullable=False),
        sa.Column("write_lane", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("section_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("idx_events_status", "events", ["status"])
    op.create_index("idx_events_section_date", "events", ["section_date"])
    op.create_index("idx_events_topic_category", "events", ["topic_category"])
    op.create_index(
        "idx_events_write_lane",
        "events",
        ["write_lane"],
        postgresql_where=sa.text("write_lane IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_events_write_lane", table_name="events")
    op.drop_index("idx_events_topic_category", table_name="events")
    op.drop_index("idx_events_section_date", table_name="events")
    op.drop_index("idx_events_status", table_name="events")
    op.drop_table("events")
