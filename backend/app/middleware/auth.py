"""Keycloak JWT authentication middleware and dependencies."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, WebSocket, status
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)

# JWKS cache (in-memory, refreshed on key miss)
_jwks_cache: dict = {}


@dataclass
class TokenUser:
    """Represents an authenticated user extracted from a JWT token."""

    keycloak_id: str
    email: str
    display_name: str
    roles: list[str] = field(default_factory=list)
    organization_id: str | None = None


async def _fetch_jwks() -> dict:
    """Fetch JWKS from Keycloak for token verification.

    Returns:
        JWKS dictionary with signing keys.

    Raises:
        HTTPException: If JWKS endpoint is unreachable.
    """
    global _jwks_cache
    settings = get_settings()
    jwks_url = settings.resolved_jwks_url

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except httpx.HTTPError as e:
        logger.error("Failed to fetch JWKS from %s: %s", jwks_url, e)
        if _jwks_cache:
            logger.warning("Using cached JWKS keys")
            return _jwks_cache
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from e


async def _get_jwks() -> dict:
    """Get JWKS, using cache if available."""
    if _jwks_cache:
        return _jwks_cache
    return await _fetch_jwks()


def _extract_token_from_header(authorization: str | None) -> str:
    """Extract Bearer token from Authorization header.

    Args:
        authorization: The Authorization header value.

    Returns:
        The JWT token string.

    Raises:
        HTTPException: If header is missing or malformed.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


async def _decode_token(token: str) -> dict:
    """Decode and validate a Keycloak JWT token.

    Args:
        token: The raw JWT string.

    Returns:
        Decoded token payload.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    settings = get_settings()
    jwks = await _get_jwks()

    try:
        # Get the signing key from JWKS
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        rsa_key = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            # Key not found — refresh JWKS (key rotation)
            jwks = await _fetch_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find signing key",
            )

        # Accept tokens issued for the API client or the web SPA client.
        # python-jose only accepts a single audience string, so we verify
        # manually after decoding.
        payload: dict[str, Any] = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_at_hash": False, "verify_aud": False, "verify_iss": False},
        )

        token_issuer = str(payload.get("iss", "")).rstrip("/")
        if token_issuer not in settings.accepted_keycloak_issuers:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issuer not accepted",
            )

        # Manual audience check: token must contain at least one accepted aud
        accepted = {settings.keycloak_client_id, "horus-web"}
        token_aud = payload.get("aud", [])
        if isinstance(token_aud, str):
            token_aud = [token_aud]
        if not accepted.intersection(token_aud):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token audience not accepted",
            )

        return payload

    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def _extract_user_from_payload(payload: dict) -> TokenUser:
    """Extract TokenUser from decoded JWT payload.

    Args:
        payload: Decoded JWT claims.

    Returns:
        TokenUser with user details and roles.
    """
    # Extract realm roles
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    return TokenUser(
        keycloak_id=payload.get("sub", ""),
        email=payload.get("email", ""),
        display_name=payload.get("preferred_username", payload.get("name", "")),
        roles=roles,
        organization_id=payload.get("organization_id"),
    )


async def get_current_user(request: Request) -> TokenUser:
    """FastAPI dependency: extract and validate the current user from JWT.

    Args:
        request: The incoming HTTP request.

    Returns:
        TokenUser representing the authenticated user.

    Raises:
        HTTPException: If auth is enabled and token is missing/invalid.
    """
    settings = get_settings()

    if not settings.auth_enabled:
        return TokenUser(
            keycloak_id="dev-user",
            email="dev@horusone.app",
            display_name="Dev User",
            roles=["platform-admin"],
            organization_id=None,
        )

    authorization = request.headers.get("authorization")
    token = _extract_token_from_header(authorization)
    payload = await _decode_token(token)
    return _extract_user_from_payload(payload)


async def get_current_user_ws(websocket: WebSocket) -> TokenUser:
    """WebSocket dependency: extract user from token query param or first message.

    Args:
        websocket: The WebSocket connection.

    Returns:
        TokenUser representing the authenticated user.

    Raises:
        HTTPException: If auth is enabled and token is missing/invalid.
    """
    settings = get_settings()

    if not settings.auth_enabled:
        return TokenUser(
            keycloak_id="dev-user",
            email="dev@horusone.app",
            display_name="Dev User",
            roles=["platform-admin"],
            organization_id=None,
        )

    # Try token from query param (WebSocket doesn't support auth headers easily)
    token = websocket.query_params.get("token")
    if not token:
        # Try from Sec-WebSocket-Protocol header
        token = websocket.headers.get("authorization", "").replace("Bearer ", "")

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebSocket authentication required",
        )

    payload = await _decode_token(token)
    return _extract_user_from_payload(payload)


# Typed dependency aliases
CurrentUser = Annotated[TokenUser, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[[CurrentUser], Awaitable[TokenUser]]:
    """Create a dependency that requires the user to have at least one of the given roles.

    Args:
        roles: Role names to check (e.g., "platform-admin", "org-admin").

    Returns:
        A FastAPI dependency function.
    """

    async def _check_role(user: CurrentUser) -> TokenUser:
        if not any(role in user.roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return _check_role


RequireAdmin = Annotated[TokenUser, Depends(require_role("platform-admin"))]
RequireOrgAdmin = Annotated[TokenUser, Depends(require_role("platform-admin", "org-admin"))]
RequireInstructor = Annotated[
    TokenUser, Depends(require_role("platform-admin", "org-admin", "instructor"))
]
