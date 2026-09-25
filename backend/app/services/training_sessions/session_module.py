"""Persistent, provenance-emitting lifecycle module for training sessions."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.types import LLMModule
from app.models.training_session import TrainingSession
from app.services.llm.graphs.live_session_graph import build_live_session_graph
from app.services.llm.graphs.scoring_graph import build_scoring_graph
from app.services.llm.graphs.validation_graph import (
    KnowledgeRetriever,
    build_validation_graph,
)
from app.services.llm.scenes.registry import SceneConfig, SceneRegistry
from app.services.llm.state import HorusState, SessionPhase
from app.services.training_sessions.session_store import SessionStore
from app.services.training_sessions.trace import TraceRecorder
from app.services.training_sessions.types import (
    Debrief,
    EndSessionCommand,
    ExchangeResult,
    SendTransmissionCommand,
    SessionSnapshot,
    StartSessionCommand,
)

logger = logging.getLogger(__name__)
_INTERNAL_TENANT_ID = uuid.UUID(int=0)


class MissingOrgError(PermissionError):
    """Raised when tenant context is required but was not supplied."""


class SessionNotFoundError(KeyError):
    """Raised when no persisted state exists for a tenant/session pair."""


class SessionPendingInstructorError(RuntimeError):
    """Raised when a transmission arrives during instructor review."""


class TrainingSessionModule:
    """Own the complete persisted lifecycle of one training session."""

    def __init__(
        self,
        store: SessionStore,
        trace: TraceRecorder,
        scenes: SceneRegistry,
        llm: LLMModule,
        db_session_factory: Callable[[], AsyncSession],
        knowledge: KnowledgeRetriever | None = None,
        interrupt_before_response: bool = False,
        require_org: bool = True,
    ) -> None:
        self._store = store
        self._trace = trace
        self._scenes = scenes
        self._llm = llm
        self._db_session_factory = db_session_factory
        self._require_org = require_org
        self._validation_graph = build_validation_graph(knowledge)
        self._scoring_graph = build_scoring_graph()
        self._interrupt_before_response = interrupt_before_response
        self._live_graphs: dict[str, Any] = {}

    async def start(self, command: StartSessionCommand) -> SessionSnapshot:
        """Validate a flight plan, persist initial state, and snapshot its Scene."""
        storage_org_id = self._start_storage_org_id(command.org_id)
        scene = self._scenes.get(command.scene_version)
        initial_state: HorusState = {
            "messages": [],
            "session_id": str(command.session_id),
            "user_id": str(command.user_id) if command.user_id else None,
            "phase": SessionPhase.INGESTION.value,
            "flight_plan": command.flight_plan,
            "weather": None,
            "fuel_state": None,
            "route_info": None,
            "airspace_info": None,
            "aircraft_performance": None,
            "validation_results": [],
            "validation_passed": False,
            "pilot_message": None,
            "atc_response": None,
            "exchange_count": 0,
            "current_waypoint_index": 0,
            "session_phase_detail": "briefing",
            "performance_notes": [],
            "is_emergency": False,
            "scoring": None,
            "badges_earned": [],
            "language": command.language,
            "context": {},
            "scene_version": scene.version,
            "prompt_version": scene.version,
            "retrieved_chunk_ids": [],
            "llm_provider": "",
            "llm_model": "",
            "llm_fallback_used": False,
            "pending_instructor": False,
        }

        result = dict(await self._validation_graph.ainvoke(initial_state))
        result["pending_instructor"] = False
        await self._store.save(storage_org_id, command.session_id, result, False)
        await self._write_scene_snapshot(command.session_id, scene)
        await self._emit(
            command.session_id,
            "session_started",
            self._event_provenance(
                result,
                graph="validation",
                node="check_all_passed",
                validation_passed=bool(result.get("validation_passed", False)),
            ),
            command.org_id,
            command.user_id,
        )
        return self._snapshot_from_state(command.session_id, result)

    async def send(self, command: SendTransmissionCommand) -> ExchangeResult:
        """Process one pilot transmission against persisted graph state."""
        org_id = self._required_org_id(command.org_id)
        stored = await self._load(org_id, command.session_id)
        state = stored.values
        if stored.pending_instructor or state.get("pending_instructor", False):
            raise SessionPendingInstructorError(
                f"Session {command.session_id} is awaiting instructor review"
            )

        state["pilot_message"] = command.pilot_message
        state["phase"] = SessionPhase.ACTIVE.value
        state["context"] = {
            **(state.get("context") or {}),
            **(command.context_overrides or {}),
        }
        result, interrupted = await self._run_live_graph(state)
        result["pending_instructor"] = interrupted
        await self._store.save(org_id, command.session_id, result, interrupted)

        if interrupted:
            await self._emit(
                command.session_id,
                "awaiting_instructor",
                self._event_provenance(
                    result,
                    graph="live",
                    node="generate_atc_response",
                ),
                org_id,
                self._state_user_id(result),
            )
            return self._exchange_result(result, atc_response="", pending=True)

        await self._emit(
            command.session_id,
            "exchange_completed",
            self._event_provenance(
                result,
                graph="live",
                node="generate_atc_response",
                provider=str(result.get("llm_provider") or ""),
                model=str(result.get("llm_model") or ""),
                fallback_used=bool(result.get("llm_fallback_used", False)),
                retrieved_chunk_ids=list(result.get("retrieved_chunk_ids") or []),
                instructor_overridden=False,
            ),
            org_id,
            self._state_user_id(result),
        )
        return self._exchange_result(result)

    async def await_instructor(
        self, org_id: uuid.UUID, session_id: int
    ) -> ExchangeResult | None:
        """Release a pending session and record the instructor's ATC response."""
        required_org_id = self._required_org_id(org_id)
        stored = await self._load(required_org_id, session_id)
        if not stored.pending_instructor and not stored.values.get(
            "pending_instructor", False
        ):
            return None

        state = stored.values
        state["pending_instructor"] = False
        await self._store.save(required_org_id, session_id, state, False)
        atc_response = str(state.get("atc_response") or "")
        await self._emit(
            session_id,
            "instructor_override",
            self._event_provenance(
                state,
                graph="live",
                node="generate_atc_response",
                atc_response=atc_response,
                instructor_overridden=True,
            ),
            required_org_id,
            self._state_user_id(state),
        )
        return self._exchange_result(state, pending=False)

    async def end(self, command: EndSessionCommand) -> Debrief:
        """Run deterministic scoring, persist the debrief, and emit completion."""
        org_id = self._required_org_id(command.org_id)
        stored = await self._load(org_id, command.session_id)
        state = stored.values
        state["phase"] = SessionPhase.POST_FLIGHT.value
        state["context"] = {
            **(state.get("context") or {}),
            **(command.student_stats_context or {}),
        }

        result = dict(await self._scoring_graph.ainvoke(state))
        result["pending_instructor"] = False
        await self._store.save(org_id, command.session_id, result, False)
        scoring = dict(result.get("scoring") or {})
        badges_earned = list(result.get("badges_earned") or [])
        await self._emit(
            command.session_id,
            "session_completed",
            self._event_provenance(
                result,
                graph="scoring",
                node="generate_report",
                scoring_summary=scoring,
                badges_earned=badges_earned,
            ),
            org_id,
            self._state_user_id(result),
        )
        return Debrief(
            scoring=scoring,
            badges_earned=badges_earned,
            report=str((result.get("context") or {}).get("report") or ""),
        )

    async def snapshot(
        self, org_id: uuid.UUID | None, session_id: int
    ) -> SessionSnapshot:
        """Return the phase, exchange count, and full state from the store."""
        storage_org_id = (
            self._required_org_id(org_id)
            if org_id is not None or self._require_org
            else _INTERNAL_TENANT_ID
        )
        stored = await self._load(storage_org_id, session_id)
        return self._snapshot_from_state(session_id, stored.values)

    async def _load(self, org_id: uuid.UUID, session_id: int):
        stored = await self._store.load(org_id, session_id)
        if stored is None:
            raise SessionNotFoundError(
                f"Session {session_id} was not found for organization {org_id}"
            )
        return stored

    async def _run_live_graph(
        self, state: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        """Run the graph and detect LangGraph's streamed static interrupt event."""
        scene_version = str(state["scene_version"])
        graph = self._live_graphs.get(scene_version)
        if graph is None:
            graph = build_live_session_graph(
                self._llm,
                self._scenes.get(scene_version),
                self._interrupt_before_response,
            )
            self._live_graphs[scene_version] = graph

        result = dict(state)
        interrupted = False
        async for mode, chunk in graph.astream(
            state, stream_mode=["values", "updates"]
        ):
            if mode == "values":
                result = dict(chunk)
            elif mode == "updates" and "__interrupt__" in chunk:
                interrupted = True
        return result, interrupted

    def _exchange_result(
        self,
        state: dict[str, Any],
        *,
        atc_response: str | None = None,
        pending: bool | None = None,
    ) -> ExchangeResult:
        return ExchangeResult(
            atc_response=(
                atc_response
                if atc_response is not None
                else str(state.get("atc_response") or "")
            ),
            is_emergency=bool(state.get("is_emergency", False)),
            exchange_count=int(state.get("exchange_count", 0)),
            pending_instructor=(
                bool(state.get("pending_instructor", False))
                if pending is None
                else pending
            ),
            citations=[],
            provider=str(state.get("llm_provider") or ""),
            model=str(state.get("llm_model") or ""),
            fallback_used=bool(state.get("llm_fallback_used", False)),
        )

    @staticmethod
    def _snapshot_from_state(
        session_id: int, state: dict[str, Any]
    ) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=session_id,
            phase=str(state.get("phase") or SessionPhase.INGESTION.value),
            exchange_count=int(state.get("exchange_count", 0)),
            state=dict(state),
        )

    @staticmethod
    def _event_provenance(state: dict[str, Any], **payload: Any) -> dict[str, Any]:
        return {
            **payload,
            "scene_version": str(state.get("scene_version") or ""),
            "prompt_version": str(state.get("prompt_version") or ""),
        }

    @staticmethod
    def _state_user_id(state: dict[str, Any]) -> uuid.UUID | None:
        value = state.get("user_id")
        if not value:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    async def _emit(
        self,
        session_id: int,
        event_type: str,
        payload: dict[str, Any],
        org_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        async with self._db_session_factory() as db:
            await self._trace.record(
                db,
                org_id,
                session_id,
                user_id,
                event_type,
                {
                    **payload,
                    "org_id": str(org_id) if org_id else None,
                    "session_id": session_id,
                },
            )
            await db.commit()

    async def _write_scene_snapshot(
        self, session_id: int, scene: SceneConfig
    ) -> None:
        """Write provenance columns when the deferred migration is installed."""
        async with self._db_session_factory() as db:
            try:
                await db.execute(
                    update(TrainingSession)
                    .where(TrainingSession.id == session_id)
                    .values(
                        scene_version=scene.version,
                        scene_snapshot=asdict(scene),
                    )
                )
                await db.commit()
            except DBAPIError as exc:
                await db.rollback()
                if getattr(exc.orig, "sqlstate", None) != "42703":
                    raise
                logger.warning(
                    "TrainingSession Scene provenance columns are unavailable; "
                    "deferred migration must add scene_version and scene_snapshot"
                )

    def _required_org_id(self, org_id: uuid.UUID | None) -> uuid.UUID:
        if org_id is None:
            raise MissingOrgError("org_id is required for this session operation")
        return org_id

    def _start_storage_org_id(self, org_id: uuid.UUID | None) -> uuid.UUID:
        if org_id is not None:
            return org_id
        if self._require_org:
            raise MissingOrgError("org_id is required to start a training session")
        return _INTERNAL_TENANT_ID
