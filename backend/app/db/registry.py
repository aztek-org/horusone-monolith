"""Import all models to ensure they are registered with SQLAlchemy metadata.

This module must be imported before Alembic runs autogenerate.
"""

from app.models.organization import Organization  # noqa: F401
from app.models.scenario import Scenario  # noqa: F401
from app.models.seat import Seat  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_preferences import UserPreferences  # noqa: F401
from app.models.voice_log import VoiceLog  # noqa: F401

__all__ = [
    "Organization",
    "Scenario",
    "Seat",
    "TrainingSession",
    "User",
    "UserPreferences",
    "VoiceLog",
]
