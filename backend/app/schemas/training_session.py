"""Pydantic schemas for TrainingSession."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrainingSessionBase(BaseModel):
    client_id: str | None = Field(default=None, max_length=36)
    scenario_id: int | None = None
    language: str = Field(default="en", pattern="^(en|es|auto)$")


class TrainingSessionCreate(TrainingSessionBase):
    scene_version: str | None = Field(default=None, max_length=50)
    flight_plan: dict[str, Any] | None = None


class TrainingSessionResponse(TrainingSessionBase):
    id: int
    status: str
    scene_version: str | None = None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class TrainingSessionEventResponse(BaseModel):
    """Audit event record for session lifecycle timeline."""

    id: uuid.UUID
    session_id: int
    user_id: uuid.UUID | None
    org_id: uuid.UUID | None
    event_type: str
    event_payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionCompletionScoring(BaseModel):
    """Normalized scoring block returned after completing a session."""

    communication_score: float
    decision_score: float
    procedure_score: float
    overall_score: float
    grade: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    summary: str = ""


class TrainingSessionCompletionResponse(BaseModel):
    """Response payload for ``POST /sessions/{id}/complete``."""

    session_id: int
    status: str
    ended_at: datetime | None
    already_completed: bool = False
    scoring: SessionCompletionScoring | None = None
    badges_earned: list[str] = Field(default_factory=list)
    report: str = ""
    replay_path: str


class ReplayTrackPoint(BaseModel):
    """Single normalized track point used by session replay."""

    index: int = Field(..., ge=0)
    timestamp: str
    lat: float
    lon: float
    altitude_ft: float
    speed_kts: float
    heading_deg: float
    vertical_speed_fpm: float
    phase: str = "unknown"
    bank_angle: float | None = None
    pitch_angle: float | None = None


class ReplayInsight(BaseModel):
    """Insight item consumed by replay timeline UI."""

    id: str
    timestamp: str
    track_index: int = Field(..., ge=0)
    category: str
    severity: str = Field(pattern="^(info|positive|warning|critical)$")
    title: str
    message: str
    score_impact: float | None = None


class ReplayVoiceLog(BaseModel):
    """Voice transcript entry consumed by replay timeline UI."""

    id: str
    timestamp: str
    track_index: int = Field(..., ge=0)
    speaker: str = Field(pattern="^(pilot|atc|system)$")
    message: str
    frequency: str | None = None
    quality_score: float | None = None


class ReplayBadge(BaseModel):
    """Badge preview included in replay scoring payload."""

    id: str
    name: str
    icon: str
    description: str


class ReplayScoringCategories(BaseModel):
    """Per-category replay scoring breakdown."""

    communication: float
    decisions: float
    procedures: float
    timing: float


class ReplayScoring(BaseModel):
    """Replay scoring summary."""

    overall_score: float
    letter_grade: str
    categories: ReplayScoringCategories
    badges: list[ReplayBadge] = Field(default_factory=list)


class ProvenanceEvent(BaseModel):
    """Provenance fields emitted for one training-session event."""

    event_type: str
    created_at: datetime
    graph: str | None = None
    node: str | None = None
    scene_version: str | None = None
    prompt_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_fallback_used: bool | None = None
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    instructor_overridden: bool | None = None


class TrainingSessionReplayResponse(BaseModel):
    """Aggregated payload returned by ``GET /sessions/{id}/replay``."""

    id: int
    scenario_id: int | None
    scenario_name: str
    status: str
    language: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None = Field(default=None, ge=0)
    track_points: list[ReplayTrackPoint] = Field(default_factory=list)
    insights: list[ReplayInsight] = Field(default_factory=list)
    voice_logs: list[ReplayVoiceLog] = Field(default_factory=list)
    scoring: ReplayScoring | None = None
    provenance: list[ProvenanceEvent] = Field(default_factory=list)
