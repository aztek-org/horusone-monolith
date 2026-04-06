"""Import all models to ensure they are registered with SQLAlchemy metadata.

This module must be imported before Alembic runs autogenerate.
"""

from app.models.assessment import (
    AssessmentResult,  # noqa: F401
    KnowledgeAssessment,  # noqa: F401
)
from app.models.content import (
    ContentArticle,  # noqa: F401
    ContentCategory,  # noqa: F401
)
from app.models.flight_plan import (
    FlightPlan,  # noqa: F401
    FlightPlanLeg,  # noqa: F401
)
from app.models.gamification import (
    Badge,  # noqa: F401
    LeaderboardSnapshot,  # noqa: F401
    UserBadge,  # noqa: F401
)
from app.models.instructor import InstructorProfile  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.scenario import Scenario  # noqa: F401
from app.models.seat import Seat  # noqa: F401
from app.models.student_stats import (
    FlightHourLog,  # noqa: F401
    ManeuverLog,  # noqa: F401
    StudentStats,  # noqa: F401
)
from app.models.training_module import TrainingModule  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401
from app.models.training_session_event import TrainingSessionEvent  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_preferences import UserPreferences  # noqa: F401
from app.models.voice_log import VoiceLog  # noqa: F401
from app.models.waypoint import (
    FlightInsight,  # noqa: F401
    ScenarioWaypoint,  # noqa: F401
    SessionTrack,  # noqa: F401
    Waypoint,  # noqa: F401
)

__all__ = [
    "AssessmentResult",
    "Badge",
    "ContentArticle",
    "ContentCategory",
    "FlightHourLog",
    "FlightInsight",
    "FlightPlan",
    "FlightPlanLeg",
    "InstructorProfile",
    "KnowledgeAssessment",
    "LeaderboardSnapshot",
    "ManeuverLog",
    "Organization",
    "Scenario",
    "ScenarioWaypoint",
    "Seat",
    "SessionTrack",
    "StudentStats",
    "TrainingModule",
    "TrainingSession",
    "TrainingSessionEvent",
    "User",
    "UserBadge",
    "UserPreferences",
    "VoiceLog",
    "Waypoint",
]
