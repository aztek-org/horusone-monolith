"""Unit tests for the TrainingSession / replay schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.training_session import (
    ProvenanceEvent,
    ReplayBadge,
    ReplayInsight,
    ReplayScoring,
    ReplayScoringCategories,
    ReplayTrackPoint,
    ReplayVoiceLog,
    SessionCompletionScoring,
    TrainingSessionBase,
    TrainingSessionCompletionResponse,
    TrainingSessionCreate,
    TrainingSessionReplayResponse,
)


class TestTrainingSessionBase:
    def test_defaults(self) -> None:
        base = TrainingSessionBase()
        assert base.client_id is None
        assert base.scenario_id is None
        assert base.language == "en"

    @pytest.mark.parametrize("language", ["en", "es", "auto"])
    def test_accepts_supported_languages(self, language: str) -> None:
        assert TrainingSessionBase(language=language).language == language

    def test_rejects_unsupported_language(self) -> None:
        with pytest.raises(ValidationError, match="language"):
            TrainingSessionBase(language="fr")

    def test_client_id_respects_max_length(self) -> None:
        with pytest.raises(ValidationError, match="client_id"):
            TrainingSessionBase(client_id="x" * 37)

    def test_create_accepts_flight_plan_and_scene_version(self) -> None:
        create = TrainingSessionCreate(flight_plan={"departure_icao": "KJFK"})
        assert create.flight_plan == {"departure_icao": "KJFK"}
        assert create.scene_version is None


class TestCompletionSchemas:
    def test_scoring_defaults_for_lists(self) -> None:
        scoring = SessionCompletionScoring(
            communication_score=80,
            decision_score=90,
            procedure_score=70,
            overall_score=80,
            grade="B",
        )
        assert scoring.strengths == []
        assert scoring.improvements == []
        assert scoring.summary == ""

    def test_completion_response_requires_replay_path(self) -> None:
        with pytest.raises(ValidationError, match="replay_path"):
            TrainingSessionCompletionResponse(
                session_id=1, status="completed", ended_at=None
            )

    def test_completion_response_defaults(self) -> None:
        response = TrainingSessionCompletionResponse(
            session_id=1, status="completed", ended_at=None, replay_path="/replay/1"
        )
        assert response.already_completed is False
        assert response.scoring is None
        assert response.badges_earned == []


class TestReplayTrackPoint:
    def test_accepts_valid_point(self) -> None:
        point = ReplayTrackPoint(
            index=0,
            timestamp="2024-01-01T00:00:00",
            lat=40.0,
            lon=-73.0,
            altitude_ft=3000,
            speed_kts=120,
            heading_deg=90,
            vertical_speed_fpm=0,
        )
        assert point.phase == "unknown"
        assert point.bank_angle is None

    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValidationError, match="index"):
            ReplayTrackPoint(
                index=-1,
                timestamp="t",
                lat=0,
                lon=0,
                altitude_ft=0,
                speed_kts=0,
                heading_deg=0,
                vertical_speed_fpm=0,
            )


class TestReplayInsightAndVoiceLog:
    @pytest.mark.parametrize("severity", ["info", "positive", "warning", "critical"])
    def test_insight_accepts_supported_severities(self, severity: str) -> None:
        insight = ReplayInsight(
            id="i1",
            timestamp="t",
            track_index=0,
            category="c",
            severity=severity,
            title="t",
            message="m",
        )
        assert insight.severity == severity

    def test_insight_rejects_invalid_severity(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            ReplayInsight(
                id="i1",
                timestamp="t",
                track_index=0,
                category="c",
                severity="boom",
                title="t",
                message="m",
            )

    @pytest.mark.parametrize("speaker", ["pilot", "atc", "system"])
    def test_voice_log_accepts_supported_speakers(self, speaker: str) -> None:
        log = ReplayVoiceLog(
            id="v1", timestamp="t", track_index=0, speaker=speaker, message="m"
        )
        assert log.speaker == speaker

    def test_voice_log_rejects_invalid_speaker(self) -> None:
        with pytest.raises(ValidationError, match="speaker"):
            ReplayVoiceLog(
                id="v1", timestamp="t", track_index=0, speaker="robot", message="m"
            )


class TestReplayScoring:
    def test_nested_categories_and_default_badges(self) -> None:
        scoring = ReplayScoring(
            overall_score=88,
            letter_grade="B+",
            categories=ReplayScoringCategories(
                communication=90, decisions=85, procedures=88, timing=80
            ),
        )
        assert scoring.categories.decisions == 85
        assert scoring.badges == []

    def test_badge_payload(self) -> None:
        badge = ReplayBadge(id="b1", name="Smooth Talker", icon="star", description="d")
        assert badge.name == "Smooth Talker"


class TestProvenanceEvent:
    def test_defaults(self) -> None:
        event = ProvenanceEvent(event_type="session.created", created_at="2024-01-01")
        assert event.graph is None
        assert event.retrieved_chunk_ids == []
        assert event.instructor_overridden is None


class TestReplayResponse:
    def test_minimal_payload_defaults(self) -> None:
        response = TrainingSessionReplayResponse(
            id=1,
            scenario_id=None,
            scenario_name="Free Flight",
            status="completed",
            language="en",
            started_at="2024-01-01T00:00:00",
            ended_at=None,
        )
        assert response.track_points == []
        assert response.insights == []
        assert response.voice_logs == []
        assert response.scoring is None
        assert response.provenance == []
        assert response.duration_seconds is None

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(ValidationError, match="duration_seconds"):
            TrainingSessionReplayResponse(
                id=1,
                scenario_id=None,
                scenario_name="Free Flight",
                status="completed",
                language="en",
                started_at="2024-01-01T00:00:00",
                ended_at=None,
                duration_seconds=-5,
            )
