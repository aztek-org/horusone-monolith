"""Add Scene provenance columns to training sessions.

The training Session module records which Scene version produced a session and
a frozen copy of that Scene at start time.

Revision ID: e5f6a7b8c9d0
Revises: d3e4f506172
Create Date: 2026-09-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d3e4f506172"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Scene version and Scene snapshot columns."""
    op.add_column(
        "training_sessions",
        sa.Column("scene_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "training_sessions",
        sa.Column(
            "scene_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the Scene provenance columns."""
    op.drop_column("training_sessions", "scene_snapshot")
    op.drop_column("training_sessions", "scene_version")
