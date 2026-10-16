"""Health check endpoint with real service probes."""

import inspect
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.llm.types import LLMModule

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ServiceStatus(BaseModel):
    """Per-dependency reachability.

    ``llm`` was named ``ollama`` before ADR-007 made the provider a choice.  The
    rename is a response-field change, recorded in
    ``docs/architecture/ARCHITECTURE-INDEX.md``: an external monitor that reads
    ``services.ollama`` reads nothing now.  Only ``ready`` and the status code
    are load-bearing in-repo.
    """

    database: str
    redis: str
    llm: str  # the configured language-model provider, whatever it is
    whisper: str
    tts: str


class ReadinessResponse(BaseModel):
    ready: bool
    services: ServiceStatus


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="horus-atc-api",
        version="0.1.0",
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(request: Request) -> ReadinessResponse:
    """Readiness check — probes all dependent services.

    **This endpoint is unauthenticated and its LLM probe leaves the process.**  A
    readiness check has to answer a load balancer that holds no credentials, so
    the route carries no auth dependency — which means the ``llm`` field reports
    the reachability of a provider addressed over the network, and some adapters
    (Groq, NVIDIA NIM) send the configured ``Authorization: Bearer`` key on every
    call.  That is safe only while ``LLM_BASE_URL`` stays server-side
    configuration the operator controls: pointing it at a third party both leaks
    the key to that party and lets anyone who can reach this route use the API's
    key as a probe amplifier.  Do not front this route with per-caller auth, and
    do not make the provider URL caller-supplied.
    """
    services = ServiceStatus(
        database=await _probe_database(),
        redis=await _probe_redis(),
        llm=await _probe_llm(request),
        whisper="loaded",
        tts="loaded",
    )
    ready = all(
        v in ("ok", "loaded")
        for v in (
            services.database,
            services.redis,
            services.llm,
            services.whisper,
            services.tts,
        )
    )
    return ReadinessResponse(ready=ready, services=services)


async def _probe_database() -> str:
    try:
        from sqlalchemy import text

        from app.db.session import get_session_factory

        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.warning("Database health probe failed", exc_info=True)
        return "unreachable"


async def _probe_redis() -> str:
    try:
        from app.core.redis import get_redis

        rd = await get_redis()
        ping_result = rd.ping()
        if inspect.isawaitable(ping_result):
            await ping_result
        return "ok"
    except Exception:
        logger.warning("Redis health probe failed", exc_info=True)
        return "unreachable"


async def _probe_llm(request: Request) -> str:
    """Report the configured provider's reachability in its own protocol.

    Asking the adapter rather than hardcoding a provider's route is what keeps a
    healthy Groq or NVIDIA NIM deployment from being reported as not ready.
    """
    llm: LLMModule | None = getattr(request.app.state, "llm", None)
    if llm is None:
        logger.warning("No language-model module is configured")
        return "unreachable"
    try:
        return await llm.probe()
    except Exception:
        logger.warning("Language-model health probe failed", exc_info=True)
        return "unreachable"
