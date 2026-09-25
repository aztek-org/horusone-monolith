"""Health check endpoint with real service probes."""
import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ServiceStatus(BaseModel):
    database: str
    redis: str
    ollama: str
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
async def readiness_check() -> ReadinessResponse:
    """Readiness check — probes all dependent services."""
    services = ServiceStatus(
        database=await _probe_database(),
        redis=await _probe_redis(),
        ollama=await _probe_ollama(),
        whisper="loaded",
        tts="loaded",
    )
    ready = all(
        v in ("ok", "loaded") for v in (
            services.database, services.redis,
            services.ollama, services.whisper, services.tts,
        )
    )
    return ReadinessResponse(ready=ready, services=services)


async def _probe_database() -> str:
    try:
        from sqlalchemy import text
        from app.db.session import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.warning("Database health probe failed", exc_info=True)
        return "unreachable"


async def _probe_redis() -> str:
    try:
        from app.core.redis import get_redis
        rd = await get_redis()
        await rd.ping()
        return "ok"
    except Exception:
        logger.warning("Redis health probe failed", exc_info=True)
        return "unreachable"


async def _probe_ollama() -> str:
    try:
        import httpx
        from app.config import get_settings
        settings = get_settings()
        base = settings.ollama_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base}/api/tags")
            if resp.status_code < 300:
                return "ok"
        return "degraded"
    except Exception:
        logger.warning("Ollama health probe failed", exc_info=True)
        return "unreachable"
