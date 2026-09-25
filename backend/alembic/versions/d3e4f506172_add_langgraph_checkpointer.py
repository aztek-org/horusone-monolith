"""Add LangGraph Postgres checkpointer tables.

The checkpointer schema is sourced from the *installed*
``langgraph-checkpoint-postgres`` package rather than transcribed into this file:
``upgrade()`` executes ``PostgresSaver.MIGRATIONS`` as the package defines it.  A
major version could still invalidate the file in two ways, and
``pyproject.toml`` pins ``langgraph-checkpoint-postgres>=3.0.0,<4.0.0`` to exclude
both:

* **A 2.x resolution** would break ``PostgresSessionStore``, which hands the saver
  a connection pool rather than a connection
  (``app/services/training_sessions/postgres_session_store.py:35``).  In 3.x
  ``AsyncPostgresSaver``'s ``_ainternal.Conn`` is ``AsyncConnection |
  AsyncConnectionPool`` and ``get_connection`` branches on the pool; the 2.x
  signature has no such branch, so the pool object would not be usable.  This —
  not the migration statements, which are read from whatever is installed — is
  the binding constraint on the lower bound.
* **A 4.x release** could add or rewrite migrations nobody has reviewed.

Patch and minor upgrades within 3.x stay permitted, because they may extend the
migration set but are not expected to rewrite the 3.x statements.  ``uv.lock``
resolves the pin to ``3.0.5``; upgrading within the major still requires
re-reading ``PostgresSaver.MIGRATIONS``, and outside it requires editing this
constraint and re-reviewing this file.

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
    """Create the checkpointer schema from the resolved library migrations."""
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
