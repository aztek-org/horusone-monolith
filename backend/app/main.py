"""Main FastAPI application for Horus ATC Voice Communication API."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.routes import health, voice
from app.api.v1 import (
    admin,
    analytics,
    assessments,
    auth,
    content,
    flight_plans,
    gamification,
    instructors,
    knowledge,
    modules,
    preferences,
    scenarios,
    scenes,
    sessions,
    stats,
    waypoints,
)
from app.config import Settings, get_settings
from app.knowledge.retrieval import build_retriever
from app.llm.routing import build_llm
from app.observability.telemetry import configure_telemetry
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry, load_scene_configs
from app.services.training_sessions.postgres_session_store import PostgresSessionStore
from app.services.training_sessions.session_module import TrainingSessionModule
from app.services.training_sessions.session_store import InMemorySessionStore, SessionStore
from app.services.training_sessions.trace import SqlAlchemyTraceRecorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


# ---------------------------------------------------------------------------
# Catch-all error middleware — ensures CORS headers on 500s
# ---------------------------------------------------------------------------

class CatchAllErrorMiddleware(BaseHTTPMiddleware):
    """Convert unhandled exceptions into JSON 500 responses.

    This runs *inside* the CORS middleware so every response — including
    error responses — gets proper ``Access-Control-*`` headers.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled exception on %s %s: %s",
                request.method,
                request.url.path,
                exc,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security-focused HTTP headers to every response."""

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


# ---------------------------------------------------------------------------
# Composition root
# ---------------------------------------------------------------------------


def _resolve_settings(application: FastAPI) -> Settings:
    """Return the settings the application should be composed with.

    Honours ``app.dependency_overrides`` so the composition root and the routes
    it serves always agree on one settings instance.
    """
    override = application.dependency_overrides.get(get_settings)
    return override() if override is not None else get_settings()


def _build_scene_registry(app_settings: Settings) -> SceneRegistry:
    """Load the Scene registry, preferring a configured path over the packaged Scene."""
    if app_settings.scenes_path:
        return load_scene_configs(app_settings.scenes_path)
    return SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE})


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Build every long-lived collaborator once and publish it on ``app.state``."""
    from app.core.redis import close_redis
    from app.db.session import get_session_factory

    app_settings = _resolve_settings(application)
    llm = build_llm(app_settings)
    store: SessionStore
    if app_settings.environment == "production":
        store = PostgresSessionStore(app_settings.database_url)
        await store.setup()
    else:
        store = InMemorySessionStore()
    scenes = _build_scene_registry(app_settings)
    retriever = build_retriever(app_settings, get_session_factory, llm)
    trace = SqlAlchemyTraceRecorder()

    application.state.settings = app_settings
    application.state.llm = llm
    application.state.session_store = store
    application.state.scene_registry = scenes
    application.state.retriever = retriever
    application.state.trace_recorder = trace
    application.state.session_module = TrainingSessionModule(
        store,
        trace,
        scenes,
        llm,
        db_session_factory=get_session_factory(),
        knowledge=retriever,
        require_org=app_settings.environment == "production",
    )

    logger.info(
        "Horus ATC API started (environment=%s, llm=%s, store=%s)",
        app_settings.environment,
        llm.provider,
        type(store).__name__,
    )
    try:
        yield
    finally:
        logger.info("Shutting down Horus ATC API...")
        try:
            await close_redis()
        finally:
            try:
                provider = otel_trace.get_tracer_provider()
                if isinstance(provider, TracerProvider):
                    provider.shutdown()
            except Exception:
                logger.warning(
                    "OpenTelemetry provider shutdown failed; continuing shutdown.",
                    exc_info=True,
                )


# Create FastAPI app
app = FastAPI(
    title="Horus ATC Voice Communication API",
    description="Real-time bi-directional voice communication system for Air Traffic Control simulation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware stack (last added = outermost).
# Order: CORSMiddleware (outer) → CatchAllErrorMiddleware (inner) → routes
app.add_middleware(CatchAllErrorMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(SecurityHeadersMiddleware)

# Instrument before Starlette's first ASGI invocation builds middleware_stack.
# Calling this from the lifespan is too late: the lifespan itself is an ASGI
# invocation, so instrument_app() would patch a stack that is already built.
configure_telemetry(settings.trace, environment=settings.environment, app=app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(voice.router, tags=["Voice"])

# API v1 routes
api_v1_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(modules.router, prefix=api_v1_prefix)
app.include_router(preferences.router, prefix=api_v1_prefix)
app.include_router(scenarios.router, prefix=api_v1_prefix)
app.include_router(scenes.router, prefix=api_v1_prefix)
app.include_router(sessions.router, prefix=api_v1_prefix)
app.include_router(admin.router, prefix=api_v1_prefix)
app.include_router(analytics.router, prefix=api_v1_prefix)
app.include_router(stats.router, prefix=api_v1_prefix)
app.include_router(content.router, prefix=api_v1_prefix)
app.include_router(waypoints.router, prefix=api_v1_prefix)
app.include_router(flight_plans.router, prefix=api_v1_prefix)
app.include_router(instructors.router, prefix=api_v1_prefix)
app.include_router(gamification.router, prefix=api_v1_prefix)
app.include_router(assessments.router, prefix=api_v1_prefix)
app.include_router(knowledge.router, prefix=api_v1_prefix)


@app.get("/")
async def root() -> dict:
    """Root endpoint.

    Returns:
        API information
    """
    return {
        "name": "Horus ATC Voice Communication API",
        "version": "0.1.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "voice_websocket": "/ws/voice",
            "docs": "/docs",
            "api_v1": {
                "modules": "/api/v1/modules",
                "scenarios": "/api/v1/scenarios",
                "sessions": "/api/v1/sessions",
                "stats": "/api/v1/stats",
                "content": "/api/v1/content",
                "waypoints": "/api/v1/waypoints",
                "flight_plans": "/api/v1/flight-plans",
                "instructors": "/api/v1/instructors",
                "gamification": "/api/v1/gamification",
                "assessments": "/api/v1/assessments",
                "knowledge": "/api/v1/knowledge",
                "admin": "/api/v1/admin",
                "analytics": "/api/v1/analytics",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
