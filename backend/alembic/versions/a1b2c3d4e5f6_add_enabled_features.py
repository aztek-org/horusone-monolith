"""Add enabled_features JSONB column to organizations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "fac62be749f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "enabled_features",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"hangar\",\"squawk\",\"tower\"]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "enabled_features")
