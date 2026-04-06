"""add training session events

Revision ID: c7d3a9e1f4b5
Revises: f1b6c3d9a712
Create Date: 2026-04-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d3a9e1f4b5"
down_revision: str | Sequence[str] | None = "f1b6c3d9a712"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create training session event audit table."""
    op.create_table(
        "training_session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "event_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["training_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_training_session_events_event_type"),
        "training_session_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_session_events_org_id"),
        "training_session_events",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_session_events_session_id"),
        "training_session_events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_session_events_user_id"),
        "training_session_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop training session event audit table."""
    op.drop_index(op.f("ix_training_session_events_user_id"), table_name="training_session_events")
    op.drop_index(op.f("ix_training_session_events_session_id"), table_name="training_session_events")
    op.drop_index(op.f("ix_training_session_events_org_id"), table_name="training_session_events")
    op.drop_index(op.f("ix_training_session_events_event_type"), table_name="training_session_events")
    op.drop_table("training_session_events")
