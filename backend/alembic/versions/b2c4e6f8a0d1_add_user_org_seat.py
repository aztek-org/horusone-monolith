"""Add User, Organization, Seat models and update existing tables.

Revision ID: b2c4e6f8a0d1
Revises: a057912b7338
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b2c4e6f8a0d1"
down_revision = "a057912b7338"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index("ix_users_keycloak_id", "users", ["keycloak_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.String(2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_seats", sa.Integer(), nullable=False, server_default=sa.text("50")),
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
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Create seats table
    op.create_table(
        "seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'student'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_seat_user_org"),
    )
    op.create_index("ix_seats_user_id", "seats", ["user_id"])
    op.create_index("ix_seats_organization_id", "seats", ["organization_id"])

    # Add org/user columns to scenarios
    op.add_column(
        "scenarios",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "scenarios",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_scenarios_org_id", "scenarios", "organizations", ["org_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_scenarios_created_by", "scenarios", "users", ["created_by"], ["id"]
    )
    op.create_index("ix_scenarios_org_id", "scenarios", ["org_id"])

    # Add org/user columns to training_sessions, make client_id nullable
    op.alter_column("training_sessions", "client_id", existing_type=sa.String(36), nullable=True)
    op.add_column(
        "training_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "training_sessions",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_training_sessions_user_id", "training_sessions", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_training_sessions_org_id",
        "training_sessions",
        "organizations",
        ["org_id"],
        ["id"],
    )
    op.create_index("ix_training_sessions_user_id", "training_sessions", ["user_id"])
    op.create_index("ix_training_sessions_org_id", "training_sessions", ["org_id"])


def downgrade() -> None:
    # Remove training_sessions columns
    op.drop_index("ix_training_sessions_org_id", table_name="training_sessions")
    op.drop_index("ix_training_sessions_user_id", table_name="training_sessions")
    op.drop_constraint("fk_training_sessions_org_id", "training_sessions", type_="foreignkey")
    op.drop_constraint("fk_training_sessions_user_id", "training_sessions", type_="foreignkey")
    op.drop_column("training_sessions", "org_id")
    op.drop_column("training_sessions", "user_id")
    op.alter_column("training_sessions", "client_id", existing_type=sa.String(36), nullable=False)

    # Remove scenarios columns
    op.drop_index("ix_scenarios_org_id", table_name="scenarios")
    op.drop_constraint("fk_scenarios_created_by", "scenarios", type_="foreignkey")
    op.drop_constraint("fk_scenarios_org_id", "scenarios", type_="foreignkey")
    op.drop_column("scenarios", "created_by")
    op.drop_column("scenarios", "org_id")

    # Drop new tables
    op.drop_table("seats")
    op.drop_table("organizations")
    op.drop_table("users")
