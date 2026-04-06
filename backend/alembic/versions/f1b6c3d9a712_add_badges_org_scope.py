"""add badges org scope

Revision ID: f1b6c3d9a712
Revises: 9d1f4ab6c2e3
Create Date: 2026-04-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b6c3d9a712"
down_revision: str | Sequence[str] | None = "9d1f4ab6c2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add organization scope to badges."""
    op.add_column("badges", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_badges_org_id_organizations",
        "badges",
        "organizations",
        ["org_id"],
        ["id"],
    )
    op.create_index(op.f("ix_badges_org_id"), "badges", ["org_id"], unique=False)
    op.execute("ALTER TABLE badges DROP CONSTRAINT IF EXISTS badges_name_key")
    op.execute("ALTER TABLE badges DROP CONSTRAINT IF EXISTS uq_badges_name")
    op.execute("DROP INDEX IF EXISTS ix_badges_slug")
    op.create_index(op.f("ix_badges_slug"), "badges", ["slug"], unique=False)
    op.create_index(
        "uq_badges_slug_shared",
        "badges",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("org_id IS NULL"),
    )
    op.create_index(
        "uq_badges_slug_org",
        "badges",
        ["org_id", "slug"],
        unique=True,
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )
    op.create_index(
        "uq_badges_name_shared",
        "badges",
        ["name"],
        unique=True,
        postgresql_where=sa.text("org_id IS NULL"),
    )
    op.create_index(
        "uq_badges_name_org",
        "badges",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("org_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove organization scope from badges."""
    op.drop_index("uq_badges_name_org", table_name="badges")
    op.drop_index("uq_badges_name_shared", table_name="badges")
    op.drop_index("uq_badges_slug_org", table_name="badges")
    op.drop_index("uq_badges_slug_shared", table_name="badges")
    op.drop_index(op.f("ix_badges_slug"), table_name="badges")
    op.create_index(op.f("ix_badges_slug"), "badges", ["slug"], unique=True)
    op.create_unique_constraint("uq_badges_name", "badges", ["name"])
    op.drop_index(op.f("ix_badges_org_id"), table_name="badges")
    op.drop_constraint("fk_badges_org_id_organizations", "badges", type_="foreignkey")
    op.drop_column("badges", "org_id")
