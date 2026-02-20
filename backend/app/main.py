"""Main FastAPI application for Horus ATC Voice Communication API."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, voice
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Horus ATC Voice Communication API",
    description="Real-time bi-directional voice communication system for Air Traffic Control simulation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Get settings
settings = get_settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(voice.router, tags=["Voice"])


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
    logger.info("Shutting down Horus ATC API...")


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
