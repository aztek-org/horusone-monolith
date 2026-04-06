"""Main FastAPI application for Horus ATC Voice Communication API."""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    modules,
    preferences,
    scenarios,
    sessions,
    stats,
    waypoints,
)
from app.config import get_settings

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


# Create FastAPI app
app = FastAPI(
    title="Horus ATC Voice Communication API",
    description="Real-time bi-directional voice communication system for Air Traffic Control simulation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
)
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(voice.router, tags=["Voice"])

# API v1 routes
api_v1_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(modules.router, prefix=api_v1_prefix)
app.include_router(preferences.router, prefix=api_v1_prefix)
app.include_router(scenarios.router, prefix=api_v1_prefix)
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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize services on startup."""
    logger.info("Starting Horus ATC API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Ollama URL: {settings.ollama_base_url}")
    logger.info(f"LLM Model: {settings.ollama_llm_model}")
    logger.info(f"Whisper Model: {settings.whisper_model}")
    logger.info(f"CORS Origins: {settings.cors_origins_list}")
    logger.info("API started successfully")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    from app.core.redis import close_redis

    logger.info("Shutting down Horus ATC API...")
    await close_redis()


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
