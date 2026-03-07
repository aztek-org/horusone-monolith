"""Import all models to ensure they are registered with SQLAlchemy metadata.

This module must be imported before Alembic runs autogenerate.
"""
from app.models.scenario import Scenario  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401
from app.models.voice_log import VoiceLog  # noqa: F401

__all__ = ["Scenario", "TrainingSession", "VoiceLog"]
