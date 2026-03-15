"""Authentication endpoints — logout with Keycloak token revocation."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_settings
from app.core.redis import get_redis
from app.middleware.auth import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Redis key TTLs
SESSION_TTL_SECONDS = 86400  # 24 hours


class LogoutRequest(BaseModel):
    """Request body for the logout endpoint.

    Attributes:
        refresh_token: Optional Keycloak refresh token to revoke.
    """

    refresh_token: str | None = None


class LogoutResponse(BaseModel):
    """Response body for the logout endpoint.

    Attributes:
        message: Human-readable result message.
    """

    message: str


class SessionCreateRequest(BaseModel):
    """Request body for creating a session cache entry.

    Attributes:
        access_token: The raw access token to hash and store.
    """

    access_token: str


class SessionCreateResponse(BaseModel):
    """Response body after caching a session.

    Attributes:
        message: Human-readable result message.
        session_key: The Redis key where the session is stored.
    """

    message: str
    session_key: str


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    body: LogoutRequest,
    user: CurrentUser,
) -> LogoutResponse:
    """Log out the current user.

    Performs two best-effort actions:
    1. Revokes the refresh token at Keycloak (if provided).
    2. Clears the Redis session cache for this user.

    Both steps are best-effort — the user is considered logged out locally
    regardless of whether Keycloak revocation succeeds.

    Args:
        body: Optional refresh token to revoke.
        user: The currently authenticated user (injected).

    Returns:
        A success message.
    """
    settings = get_settings()

    # 1. Revoke refresh token at Keycloak (best-effort)
    if body.refresh_token:
        revoke_url = f"{settings.keycloak_issuer_url}/protocol/openid-connect/revoke"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    revoke_url,
                    data={
                        "client_id": settings.keycloak_client_id,
                        "token": body.refresh_token,
                        "token_type_hint": "refresh_token",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code < 300:
                    logger.info("Keycloak token revoked for user %s", user.keycloak_id)
                else:
                    logger.warning(
                        "Keycloak revocation returned %s for user %s: %s",
                        response.status_code,
                        user.keycloak_id,
                        response.text,
                    )
        except httpx.HTTPError as exc:
            logger.warning(
                "Keycloak revocation failed for user %s: %s",
                user.keycloak_id,
                exc,
            )

    # 2. Clear Redis session cache (best-effort)
    try:
        rd = await get_redis()
        session_key = f"session:{user.keycloak_id}"
        await rd.delete(session_key)
        logger.info("Redis session cleared for user %s", user.keycloak_id)
    except Exception:
        logger.warning(
            "Failed to clear Redis session for user %s",
            user.keycloak_id,
            exc_info=True,
        )

    return LogoutResponse(message="Logged out successfully")


@router.post("/session", response_model=SessionCreateResponse)
async def create_session(
    body: SessionCreateRequest,
    user: CurrentUser,
    request: Request,
) -> SessionCreateResponse:
    """Cache session information in Redis after a successful login.

    Stores a JSON payload under ``session:{keycloak_id}`` with a 24-hour TTL
    containing a SHA-256 hash of the access token, the login timestamp, and
    the User-Agent string.

    Args:
        body: Contains the access token to hash.
        user: The currently authenticated user (injected).
        request: The incoming HTTP request (for User-Agent header).

    Returns:
        Confirmation with the Redis key used.
    """
    session_key = f"session:{user.keycloak_id}"
    token_hash = hashlib.sha256(body.access_token.encode()).hexdigest()
    user_agent = request.headers.get("user-agent", "unknown")

    session_data = {
        "token_hash": token_hash,
        "login_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": user_agent,
        "keycloak_id": user.keycloak_id,
        "email": user.email,
    }

    try:
        rd = await get_redis()
        await rd.setex(session_key, SESSION_TTL_SECONDS, json.dumps(session_data))
        logger.info("Session cached for user %s", user.keycloak_id)
    except Exception:
        logger.warning(
            "Failed to cache session for user %s",
            user.keycloak_id,
            exc_info=True,
        )

    return SessionCreateResponse(
        message="Session cached successfully",
        session_key=session_key,
    )
