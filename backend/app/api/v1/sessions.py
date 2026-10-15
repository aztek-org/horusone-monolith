"""Training session API routes with RBAC enforcement.

- ``GET  /`` — all authenticated users (role-based filtering)
- ``POST /`` — any authenticated user can start a session
- ``GET  /{session_id}`` — access verified per user / org
- ``POST /{session_id}/complete`` — end session and trigger scoring
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import can_access_org, has_role, is_platform_admin
from app.db.repositories.waypoint_repository import WaypointRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, TokenUser
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.models.user import User
from app.schemas.training_session import (
    ProvenanceEvent,
    ReplayBadge,
    ReplayInsight,
    ReplayScoring,
    ReplayScoringCategories,
    ReplayTrackPoint,
    ReplayVoiceLog,
    TrainingSessionCompletionResponse,
    TrainingSessionCreate,
    TrainingSessionEventResponse,
    TrainingSessionReplayResponse,
    TrainingSessionResponse,
)
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.audit import (
    discard_unstarted_session,
    record_session_created,
    record_session_event,
)
from app.services.training_sessions.types import (
    Debrief,
    EndSessionCommand,
    StartSessionCommand,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])
waypoint_repo = WaypointRepository()


@router.get("/", response_model=list[TrainingSessionResponse])
async def list_sessions(
    user: CurrentUser,
    org_id: UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    status_filter: Literal["active", "completed", "draft"] | None = Query(
        default=None,
        alias="status",
    ),
    scenario_id: int | None = Query(default=None, ge=1),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[TrainingSessionResponse]:
    """List training sessions visible to the current user.

    Platform admins see all sessions.  Instructors and org-admins see
    all sessions within their organization.  Students see only their
    own sessions.
    """
    query = select(TrainingSession)

    if is_platform_admin(user):
        pass  # No filter — full access
    elif has_role(user, "org-admin", "instructor"):
        if org_id:
            query = query.where(TrainingSession.org_id == org_id)
        else:
            # Instructor with no org context — own sessions only
            query = query.where(TrainingSession.user_id == local_user.id)
    else:
        # Students see only their own sessions
        query = query.where(TrainingSession.user_id == local_user.id)

    if started_after is not None and started_before is not None and started_after > started_before:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="started_after must be less than or equal to started_before",
        )
    if status_filter is not None:
        query = query.where(TrainingSession.status == status_filter)
    if scenario_id is not None:
        query = query.where(TrainingSession.scenario_id == scenario_id)
    if started_after is not None:
        query = query.where(TrainingSession.started_at >= started_after)
    if started_before is not None:
        query = query.where(TrainingSession.started_at <= started_before)

    result = await session.execute(
        query.order_by(TrainingSession.started_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())  # type: ignore[return-value]


@router.post("/", response_model=TrainingSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: TrainingSessionCreate,
    request: Request,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    org_id: UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Create a new training session.

    Requires an **active seat** in an organization.  Users without a seat
    can browse scenarios and view stats but cannot start training.

    The row and its ``created`` audit event are written in one unit of work, so
    a session can never exist without the event that explains it.  The Session
    module then starts the session through its own unit of work, which requires
    the row to be visible first.

    Everything ``start()`` would reject is rejected here first, before the
    commit, so a client error cannot leave a row that claims to exist but was
    never started.
    """
    scene_version = data.scene_version or DEFAULT_SCENE.version
    _reject_unstartable_session(request, scene_version, org_id)
    training_session = TrainingSession(
        **data.model_dump(exclude={"scene_version", "flight_plan"}),
        user_id=local_user.id,
        org_id=org_id,
        scene_version=scene_version,
    )
    session.add(training_session)
    await session.flush()
    await session.refresh(training_session)
    record_session_created(session, training_session, user_id=local_user.id)
    await session.commit()
    try:
        await request.app.state.session_module.start(
            StartSessionCommand(
                org_id=org_id,
                user_id=local_user.id,
                session_id=training_session.id,
                scene_version=scene_version,
                language=data.language,
                flight_plan=data.flight_plan or {},
            )
        )
    except Exception:
        # The row is already durable, so a start that never happened would
        # otherwise stay behind as an active session with nothing running in it.
        await discard_unstarted_session(training_session.id)
        raise
    logger.info("Created training session: %s (user=%s)", training_session.id, local_user.id)
    return training_session  # type: ignore[return-value]


def _reject_unstartable_session(request: Request, scene_version: str, org_id: UUID | None) -> None:
    """Refuse inputs the Session module could not start, before anything is written.

    ``start()`` resolves the Scene and the tenant itself, so an unknown Scene
    version or a token with no organization would otherwise surface only after
    the row and its ``created`` event had committed.  Both are client errors, and
    the catch-all error middleware flattens them to a 500.
    """
    registry: SceneRegistry = request.app.state.scene_registry
    try:
        registry.get(scene_version)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene '{scene_version}' not found",
        ) from exc

    if org_id is None and _requires_tenant(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization associated with your account",
        )


def _requires_tenant(request: Request) -> bool:
    """Whether this deployment refuses tenant-less sessions.

    Mirrors the rule the composition root gives the Session module, which would
    otherwise raise ``MissingOrgError`` — a ``PermissionError`` — after the commit.
    """
    environment: str = request.app.state.settings.environment
    return environment == "production"


@router.get("/{session_id}", response_model=TrainingSessionResponse)
async def get_session(
    session_id: int,
    user: CurrentUser,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Get a specific training session by ID.

    Users can view their own sessions.  Instructors and org-admins can
    view sessions within their organization.  Platform admins can view
    any session.
    """
    result = await session.execute(
        select(TrainingSession)
        .options(selectinload(TrainingSession.voice_logs))
        .where(TrainingSession.id == session_id)
    )
    training_session = result.scalar_one_or_none()
    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not _can_view_session(user, local_user, training_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    return training_session  # type: ignore[return-value]


@router.get("/{session_id}/events", response_model=list[TrainingSessionEventResponse])
async def get_session_events(
    session_id: int,
    user: CurrentUser,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TrainingSessionEventResponse]:
    """Get audit events for a training session, ordered oldest-first."""
    session_result = await session.execute(
        select(TrainingSession).where(TrainingSession.id == session_id)
    )
    training_session = session_result.scalar_one_or_none()
    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not _can_view_session(user, local_user, training_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    events_result = await session.execute(
        select(TrainingSessionEvent)
        .where(TrainingSessionEvent.session_id == session_id)
        .order_by(TrainingSessionEvent.created_at.asc())
    )
    return list(events_result.scalars().all())  # type: ignore[return-value]


@router.get("/{session_id}/replay", response_model=TrainingSessionReplayResponse)
async def get_session_replay(
    session_id: int,
    user: CurrentUser,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionReplayResponse:
    """Get replay payload for a training session.

    Includes normalized flight track points, timeline insights, transcript logs,
    and computed scoring so frontend replay views can render from one request.
    """
    result = await session.execute(
        select(TrainingSession)
        .options(
            selectinload(TrainingSession.scenario),
            selectinload(TrainingSession.voice_logs),
        )
        .where(TrainingSession.id == session_id)
    )
    training_session = result.scalar_one_or_none()
    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not _can_view_session(user, local_user, training_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    events_result = await session.execute(
        select(TrainingSessionEvent)
        .where(TrainingSessionEvent.session_id == session_id)
        .order_by(TrainingSessionEvent.created_at.asc())
    )
    provenance = [_provenance_from_event(event) for event in events_result.scalars().all()]

    track = await waypoint_repo.get_session_track(session, session_id)
    raw_track_points: list[dict[str, Any]] = track.track_points if track else []
    track_points = _normalize_replay_track_points(raw_track_points)

    insights_rows = await waypoint_repo.get_flight_insights(session, session_id)
    insights = _normalize_replay_insights(insights_rows, track_points)

    voice_logs = _normalize_replay_voice_logs(training_session, track_points)
    scoring = _build_replay_scoring(training_session, insights)

    duration_seconds: int | None = None
    if training_session.ended_at is not None:
        delta = training_session.ended_at - training_session.started_at
        duration_seconds = max(int(delta.total_seconds()), 0)

    return TrainingSessionReplayResponse(
        id=training_session.id,
        scenario_id=training_session.scenario_id,
        scenario_name=training_session.scenario.name
        if training_session.scenario
        else "Unknown Scenario",
        status=training_session.status,
        language=training_session.language,
        started_at=training_session.started_at,
        ended_at=training_session.ended_at,
        duration_seconds=duration_seconds,
        track_points=track_points,
        insights=insights,
        voice_logs=voice_logs,
        scoring=scoring,
        provenance=provenance,
    )


@router.post(
    "/{session_id}/complete",
    response_model=TrainingSessionCompletionResponse,
)
async def complete_session(
    session_id: int,
    request: Request,
    user: CurrentUser,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionCompletionResponse:
    """End a training session and run post-flight scoring.

    Marks the session as ``completed``, records ``ended_at``, and hands the
    persisted session state to the Session module's scoring pipeline.
    Completing an already-completed session is idempotent.
    """
    result = await session.execute(select(TrainingSession).where(TrainingSession.id == session_id))
    training_session = result.scalar_one_or_none()

    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not _can_view_session(user, local_user, training_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    if training_session.status == "completed":
        if training_session.ended_at is None:
            training_session.ended_at = datetime.now(timezone.utc)
            await session.flush()
            await session.refresh(training_session)

        logger.info(
            "Session %s completion requested but already completed (user=%s)",
            session_id,
            local_user.id,
        )
        return _build_completion_response(
            training_session=training_session,
            debrief=None,
            already_completed=True,
        )

    if training_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session {session_id} cannot be completed from status '{training_session.status}'"
            ),
        )

    # Score first: the Session module reads the graph state it persisted, not this
    # row.  Keeping the status change in the route's own uncommitted unit of work
    # means a scoring failure rolls the row back to "active" instead of stranding
    # a completed session that can never produce a debrief.
    debrief = await request.app.state.session_module.end(
        EndSessionCommand(
            org_id=training_session.org_id,
            session_id=training_session.id,
        )
    )

    training_session.status = "completed"
    training_session.ended_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(training_session)

    response = _build_completion_response(
        training_session=training_session,
        debrief=debrief,
        already_completed=False,
    )
    record_session_event(
        session,
        session_id=training_session.id,
        user_id=local_user.id,
        org_id=training_session.org_id,
        event_type="completed",
        event_payload={
            "grade": response.scoring.grade if response.scoring else None,
            "overall_score": response.scoring.overall_score if response.scoring else None,
            "badges_earned": response.badges_earned,
            "already_completed": False,
        },
    )

    logger.info(
        "Session %s completed (user=%s, grade=%s)",
        session_id,
        local_user.id,
        response.scoring.grade if response.scoring else "N/A",
    )

    return response


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_completion_response(
    training_session: TrainingSession,
    debrief: Debrief | None,
    already_completed: bool,
) -> TrainingSessionCompletionResponse:
    """Build normalized completion payload for API responses."""
    scoring = _normalize_completion_scoring(debrief.scoring if debrief else None)
    badges_earned = _normalize_badges(debrief.badges_earned if debrief else None)
    report = debrief.report if debrief else ""

    return TrainingSessionCompletionResponse(
        session_id=training_session.id,
        status="completed",
        ended_at=training_session.ended_at,
        already_completed=already_completed,
        scoring=scoring,
        badges_earned=badges_earned,
        report=report,
        replay_path=f"/session/{training_session.id}",
    )


def _normalize_completion_scoring(raw_scoring: Any) -> dict[str, Any] | None:
    """Normalize the scoring block produced by the Session module."""
    if not isinstance(raw_scoring, dict) or not raw_scoring:
        return None

    return {
        "communication_score": _to_float(raw_scoring.get("communication_score")),
        "decision_score": _to_float(raw_scoring.get("decision_score")),
        "procedure_score": _to_float(raw_scoring.get("procedure_score")),
        "overall_score": _to_float(raw_scoring.get("overall_score")),
        "grade": str(raw_scoring.get("grade", "N/A")),
        "strengths": _normalize_string_list(raw_scoring.get("strengths")),
        "improvements": _normalize_string_list(raw_scoring.get("improvements")),
        "summary": str(raw_scoring.get("summary", "")),
    }


def _normalize_badges(raw_badges: Any) -> list[str]:
    """Normalize badge list from scoring result."""
    if not isinstance(raw_badges, list):
        return []
    return [str(badge) for badge in raw_badges if badge is not None]


def _normalize_string_list(raw_values: Any) -> list[str]:
    """Normalize any list-like value to a list of strings."""
    if not isinstance(raw_values, list):
        return []
    return [str(item) for item in raw_values if item is not None]


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert unknown numeric input to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _provenance_from_event(event: TrainingSessionEvent) -> ProvenanceEvent:
    """Expose persisted provenance while tolerating legacy lifecycle events."""
    payload = event.event_payload
    raw_chunk_ids = payload.get("retrieved_chunk_ids")
    retrieved_chunk_ids = (
        [str(chunk_id) for chunk_id in raw_chunk_ids] if isinstance(raw_chunk_ids, list) else []
    )
    return ProvenanceEvent(
        event_type=event.event_type,
        created_at=event.created_at,
        graph=payload.get("graph"),
        node=payload.get("node"),
        scene_version=payload.get("scene_version"),
        prompt_version=payload.get("prompt_version"),
        llm_provider=payload.get("provider"),
        llm_model=payload.get("model"),
        llm_fallback_used=payload.get("fallback_used"),
        retrieved_chunk_ids=retrieved_chunk_ids,
        instructor_overridden=payload.get("instructor_overridden"),
    )


def _can_view_session(
    token_user: TokenUser,
    local_user: User,
    training_session: TrainingSession,
) -> bool:
    """Check whether the user can view the given training session.

    Args:
        token_user: JWT token user with roles.
        local_user: Local database User record.
        training_session: The session to check access for.

    Returns:
        True if the user is authorized to view the session.
    """
    # Platform admin — full access
    if is_platform_admin(token_user):
        return True

    # Own session
    if training_session.user_id == local_user.id:
        return True

    # Instructor or org-admin in the same org
    if training_session.org_id and has_role(token_user, "org-admin", "instructor"):
        return can_access_org(token_user, training_session.org_id)

    return False


def _normalize_replay_track_points(raw_points: list[dict[str, Any]]) -> list[ReplayTrackPoint]:
    """Normalize persisted track points to frontend replay shape."""
    normalized: list[ReplayTrackPoint] = []
    for idx, point in enumerate(raw_points):
        timestamp = point.get("timestamp")
        normalized.append(
            ReplayTrackPoint(
                index=idx,
                timestamp=(
                    str(timestamp)
                    if timestamp is not None
                    else datetime.now(timezone.utc).isoformat()
                ),
                lat=float(point.get("lat", 0.0)),
                lon=float(point.get("lon", point.get("lng", 0.0))),
                altitude_ft=float(point.get("altitude_ft", point.get("altitude", 0.0))),
                speed_kts=float(point.get("speed_kts", point.get("speed", 0.0))),
                heading_deg=float(point.get("heading_deg", point.get("heading", 0.0))),
                vertical_speed_fpm=float(
                    point.get("vertical_speed_fpm", point.get("vertical_speed", 0.0))
                ),
                phase=str(point.get("phase", "unknown")),
                bank_angle=(
                    float(point["bank_angle"]) if point.get("bank_angle") is not None else None
                ),
                pitch_angle=(
                    float(point["pitch_angle"]) if point.get("pitch_angle") is not None else None
                ),
            )
        )
    return normalized


def _closest_track_index(track_points: list[ReplayTrackPoint], seconds: float) -> int:
    """Map seconds-from-start to nearest track index."""
    if not track_points:
        return 0

    timestamps: list[datetime] = []
    for point in track_points:
        try:
            timestamps.append(datetime.fromisoformat(point.timestamp.replace("Z", "+00:00")))
        except ValueError:
            return 0

    if not timestamps:
        return 0

    origin = timestamps[0]
    target = origin.timestamp() + max(seconds, 0.0)
    best_idx = 0
    best_distance = abs(timestamps[0].timestamp() - target)

    for idx, ts in enumerate(timestamps[1:], start=1):
        distance = abs(ts.timestamp() - target)
        if distance < best_distance:
            best_distance = distance
            best_idx = idx

    return best_idx


def _normalize_replay_insights(
    insights_rows: list[Any],
    track_points: list[ReplayTrackPoint],
) -> list[ReplayInsight]:
    """Normalize flight-insight rows to replay timeline items."""
    normalized: list[ReplayInsight] = []
    severity_map = {
        "low": "info",
        "medium": "warning",
        "high": "critical",
        "critical": "critical",
        "success": "positive",
    }
    category_map = {
        "comms": "communication",
        "communication": "communication",
        "decision": "decision",
        "procedure": "procedure",
        "timing": "timing",
        "safety": "safety",
    }

    for insight in insights_rows:
        raw_type = str(getattr(insight, "type", "procedure")).lower()
        raw_severity = str(getattr(insight, "severity", "info")).lower()
        timestamp_in_session = float(getattr(insight, "timestamp_in_session", 0.0))
        track_index = _closest_track_index(track_points, timestamp_in_session)

        timestamp = (
            track_points[track_index].timestamp
            if track_points and track_index < len(track_points)
            else datetime.now(timezone.utc).isoformat()
        )

        normalized.append(
            ReplayInsight(
                id=str(getattr(insight, "id")),
                timestamp=timestamp,
                track_index=track_index,
                category=category_map.get(raw_type, raw_type if raw_type else "procedure"),
                severity=severity_map.get(raw_severity, "info"),
                title=str(getattr(insight, "title", "Insight")),
                message=str(getattr(insight, "description", "")),
                score_impact=None,
            )
        )
    return normalized


def _normalize_replay_voice_logs(
    training_session: TrainingSession,
    track_points: list[ReplayTrackPoint],
) -> list[ReplayVoiceLog]:
    """Normalize voice logs and assign each entry to nearest track index."""
    logs = sorted(training_session.voice_logs, key=lambda entry: entry.created_at)
    if not logs:
        return []

    if not track_points:
        return [
            ReplayVoiceLog(
                id=str(log.id),
                timestamp=log.created_at.isoformat(),
                track_index=idx,
                speaker=log.role if log.role in {"pilot", "atc"} else "system",
                message=log.transcript,
                frequency=None,
                quality_score=None,
            )
            for idx, log in enumerate(logs)
        ]

    first_track_time: datetime | None = None
    try:
        first_track_time = datetime.fromisoformat(track_points[0].timestamp.replace("Z", "+00:00"))
    except ValueError:
        first_track_time = None

    normalized: list[ReplayVoiceLog] = []
    for idx, log in enumerate(logs):
        track_index = min(idx, len(track_points) - 1)
        if first_track_time is not None:
            seconds = max((log.created_at - first_track_time).total_seconds(), 0.0)
            track_index = _closest_track_index(track_points, seconds)

        normalized.append(
            ReplayVoiceLog(
                id=str(log.id),
                timestamp=log.created_at.isoformat(),
                track_index=track_index,
                speaker=log.role if log.role in {"pilot", "atc"} else "system",
                message=log.transcript,
                frequency=None,
                quality_score=None,
            )
        )

    return normalized


def _build_replay_scoring(
    training_session: TrainingSession,
    insights: list[ReplayInsight],
) -> ReplayScoring | None:
    """Derive a simple replay score card from session state and insight severity."""
    if training_session.status not in {"completed", "active"}:
        return None

    total = len(insights) or 1
    critical = sum(1 for item in insights if item.severity == "critical")
    warning = sum(1 for item in insights if item.severity == "warning")
    positive = sum(1 for item in insights if item.severity == "positive")

    communication = max(0.0, min(100.0, 85.0 + positive * 2.0 - warning * 4.0 - critical * 6.0))
    decisions = max(0.0, min(100.0, 82.0 - warning * 3.0 - critical * 7.0))
    procedures = max(0.0, min(100.0, 84.0 - warning * 2.5 - critical * 7.5))
    timing = max(
        0.0,
        min(100.0, 80.0 + (positive / total) * 10.0 - (critical / total) * 25.0),
    )

    overall = round((communication + decisions + procedures + timing) / 4.0, 1)
    if overall >= 95:
        grade = "A+"
    elif overall >= 90:
        grade = "A"
    elif overall >= 85:
        grade = "B+"
    elif overall >= 80:
        grade = "B"
    elif overall >= 75:
        grade = "C+"
    elif overall >= 70:
        grade = "C"
    elif overall >= 60:
        grade = "D"
    else:
        grade = "F"

    badges: list[ReplayBadge] = []
    if training_session.status == "completed":
        if critical == 0 and overall >= 85:
            badges.append(
                ReplayBadge(
                    id="clean-ops",
                    name="Clean Ops",
                    icon="✅",
                    description="Completed without critical replay insights.",
                )
            )
        if positive > 0:
            badges.append(
                ReplayBadge(
                    id="good-comms",
                    name="Good Comms",
                    icon="📡",
                    description="Positive communication events captured in replay.",
                )
            )

    return ReplayScoring(
        overall_score=overall,
        letter_grade=grade,
        categories=ReplayScoringCategories(
            communication=round(communication, 1),
            decisions=round(decisions, 1),
            procedures=round(procedures, 1),
            timing=round(timing, 1),
        ),
        badges=badges,
    )
