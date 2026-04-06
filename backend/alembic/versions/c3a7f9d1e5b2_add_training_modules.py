"""add training modules

Revision ID: c3a7f9d1e5b2
Revises: ee0e6be2458f
Create Date: 2026-03-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a7f9d1e5b2"
down_revision: str | Sequence[str] | None = "ee0e6be2458f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create training_modules and module_scenarios tables."""
    op.create_table(
        "training_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("difficulty_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_training_modules_name", "training_modules", ["name"])
    op.create_index("ix_training_modules_org_id", "training_modules", ["org_id"])

    op.create_table(
        "module_scenarios",
        sa.Column(
            "module_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("module_id", "scenario_id"),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["training_modules.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Drop module_scenarios and training_modules tables."""
    op.drop_table("module_scenarios")
    op.drop_index("ix_training_modules_org_id", table_name="training_modules")
    op.drop_index("ix_training_modules_name", table_name="training_modules")
    op.drop_table("training_modules")
