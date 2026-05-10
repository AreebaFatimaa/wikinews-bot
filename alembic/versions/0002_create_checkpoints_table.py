"""create checkpoints table

Revision ID: 0002_create_checkpoints
Revises: 0001_create_events
Create Date: 2026-05-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_create_checkpoints"
down_revision = "0001_create_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkpoints",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("since_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_rev_id", sa.BigInteger(), nullable=True),
        sa.Column("events_processed", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("checkpoints")
