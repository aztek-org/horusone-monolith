"""Add LangGraph Postgres checkpointer tables.

The checkpointer schema is sourced from the installed
``langgraph-checkpoint-postgres==3.0.5`` package rather than copied into this
migration.

Revision ID: d3e4f506172
Revises: c2d3e4f5061
Create Date: 2026-09-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from langgraph.checkpoint.postgres import PostgresSaver

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f506172"
down_revision: str | Sequence[str] | None = "c2d3e4f5061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the checkpointer schema from the pinned library migrations."""
    # CREATE INDEX CONCURRENTLY in the library migrations cannot run inside
    # Alembic's transaction. Run the library statements independently, while
    # retaining the exact SQL supplied by the pinned package.
    bind = op.get_bind()
    bind.commit()
    bind.execution_options(isolation_level="AUTOCOMMIT")
    for migration in PostgresSaver.MIGRATIONS:
        op.execute(migration)

    migrations_table = sa.table("checkpoint_migrations", sa.column("v", sa.Integer()))
    op.bulk_insert(
        migrations_table,
        [{"v": version} for version in range(len(PostgresSaver.MIGRATIONS))],
    )
    bind.commit()


def downgrade() -> None:
    """Drop the checkpointer tables in dependency order."""
    bind = op.get_bind()
    bind.commit()
    bind.execution_options(isolation_level="AUTOCOMMIT")
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoints")
    op.drop_table("checkpoint_migrations")
    bind.commit()
