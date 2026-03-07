"""initial_schema

Revision ID: a057912b7338
Revises: 
Create Date: 2026-03-06 22:57:11.775460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a057912b7338'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("airport_icao", sa.String(length=4), nullable=False),
        sa.Column("runway", sa.String(length=10), nullable=False),
        sa.Column("weather_preset", sa.String(length=10), nullable=False),
        sa.Column("phase", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scenarios_airport_icao"), "scenarios", ["airport_icao"])
    op.create_index(op.f("ix_scenarios_name"), "scenarios", ["name"])

    op.create_table(
        "training_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_sessions_client_id"), "training_sessions", ["client_id"])

    op.create_table(
        "voice_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("audio_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["training_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_voice_logs_session_id"), "voice_logs", ["session_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_voice_logs_session_id"), table_name="voice_logs")
    op.drop_table("voice_logs")
    op.drop_index(op.f("ix_training_sessions_client_id"), table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index(op.f("ix_scenarios_name"), table_name="scenarios")
    op.drop_index(op.f("ix_scenarios_airport_icao"), table_name="scenarios")
    op.drop_table("scenarios")
