"""Add the pgvector extension.

Revision ID: b1c2d3e4f506
Revises: dcc247c7ad05
Create Date: 2026-09-25 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f506"
down_revision: str | Sequence[str] | None = "dcc247c7ad05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable PostgreSQL vector support."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Disable PostgreSQL vector support."""
    op.execute("DROP EXTENSION IF EXISTS vector")
