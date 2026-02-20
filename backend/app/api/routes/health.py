"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "horus-atc-api",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check for services.

    Returns:
        Readiness status
    """
    # TODO: Add checks for Ollama, Whisper, TTS availability
    return {
        "ready": True,
        "services": {
            "ollama": "unknown",
            "whisper": "loaded",
            "tts": "loaded",
        },
    }
