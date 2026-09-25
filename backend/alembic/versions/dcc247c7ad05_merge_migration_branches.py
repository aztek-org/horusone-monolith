"""Merge migration branches

Revision ID: dcc247c7ad05
Revises: a1b2c3d4e5f6, c7d3a9e1f4b5
Create Date: 2026-08-15 17:16:13.840025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcc247c7ad05'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'c7d3a9e1f4b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
