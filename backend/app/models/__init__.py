"""SQLAlchemy ORM models for Horus ATC API."""

from app.models.assessment import AssessmentResult, KnowledgeAssessment
from app.models.content import ContentArticle, ContentCategory
from app.models.flight_plan import FlightPlan, FlightPlanLeg
from app.models.gamification import Badge, LeaderboardSnapshot, UserBadge
from app.models.instructor import InstructorProfile
from app.models.organization import Organization
from app.models.scenario import Scenario
from app.models.seat import Seat
from app.models.student_stats import FlightHourLog, ManeuverLog, StudentStats
from app.models.training_module import TrainingModule
from app.models.training_session import TrainingSession
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.models.voice_log import VoiceLog
from app.models.waypoint import (
    FlightInsight,
    ScenarioWaypoint,
    SessionTrack,
    Waypoint,
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
    "User",
    "UserBadge",
    "UserPreferences",
    "VoiceLog",
    "Waypoint",
]
