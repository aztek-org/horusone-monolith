"""Add the training-session event retention index.

Revision ID: f5061728394
Revises: e5f6a7b8c9d0
Create Date: 2026-09-25 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5061728394"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Index event timestamps used by the retention cutoff query."""
    op.create_index(
        "ix_training_session_events_created_at",
        "training_session_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the training-session event retention index."""
    op.drop_index(
        "ix_training_session_events_created_at",
        table_name="training_session_events",
    )
