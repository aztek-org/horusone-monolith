"""add organization billing fields

Revision ID: 9d1f4ab6c2e3
Revises: fac62be749f8
Create Date: 2026-04-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d1f4ab6c2e3"
down_revision: str | Sequence[str] | None = "fac62be749f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add billing metadata columns to organizations."""
    op.add_column(
        "organizations",
        sa.Column("billing_plan", sa.String(length=32), server_default="starter", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("billing_status", sa.String(length=32), server_default="trial", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("billing_cycle", sa.String(length=16), server_default="monthly", nullable=False),
    )


def downgrade() -> None:
    """Drop billing metadata columns from organizations."""
    op.drop_column("organizations", "billing_cycle")
    op.drop_column("organizations", "billing_status")
    op.drop_column("organizations", "billing_plan")
