"""Unit tests for JWT authentication middleware."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.middleware.auth import (
    TokenUser,
    _extract_token_from_header,
    _extract_user_from_payload,
    get_current_user,
    require_role,
)


# ── TokenUser dataclass ───────────────────────────────────────────────


class TestTokenUser:
    """Tests for the TokenUser dataclass."""

    def test_create_with_all_fields(self) -> None:
        user = TokenUser(
            keycloak_id="kc-123",
            email="pilot@example.com",
            display_name="Test Pilot",
            roles=["instructor", "org-admin"],
            organization_id="org-abc",
        )
        assert user.keycloak_id == "kc-123"
        assert user.email == "pilot@example.com"
        assert user.display_name == "Test Pilot"
        assert user.roles == ["instructor", "org-admin"]
        assert user.organization_id == "org-abc"

    def test_defaults(self) -> None:
        user = TokenUser(
            keycloak_id="kc-1",
            email="a@b.com",
            display_name="A",
        )
        assert user.roles == []
        assert user.organization_id is None


# ── _extract_token_from_header ─────────────────────────────────────────


class TestExtractTokenFromHeader:
    """Tests for _extract_token_from_header()."""

    def test_valid_bearer_token(self) -> None:
        token = _extract_token_from_header("Bearer eyJhbGciOi.test.token")
        assert token == "eyJhbGciOi.test.token"

    def test_missing_header_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header(None)
        assert exc_info.value.status_code == 401
        assert "Missing Authorization header" in exc_info.value.detail

    def test_empty_string_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header("")
        assert exc_info.value.status_code == 401

    def test_only_bearer_keyword_raises_401(self) -> None:
        """'Bearer' with no token after it should fail."""
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header("Bearer")
        assert exc_info.value.status_code == 401
        assert "Invalid Authorization header format" in exc_info.value.detail

    def test_wrong_scheme_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header("Basic dXNlcjpwYXNz")
        assert exc_info.value.status_code == 401
        assert "Invalid Authorization header format" in exc_info.value.detail

    def test_too_many_parts_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header("Bearer token extra")
        assert exc_info.value.status_code == 401

    def test_bearer_case_insensitive(self) -> None:
        """The code lowercases the scheme, so 'bearer' should work."""
        token = _extract_token_from_header("bearer my-token")
        assert token == "my-token"

    def test_www_authenticate_header_on_missing(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _extract_token_from_header(None)
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


# ── _extract_user_from_payload ─────────────────────────────────────────


class TestExtractUserFromPayload:
    """Tests for _extract_user_from_payload()."""

    def test_full_payload(self) -> None:
        payload = {
            "sub": "kc-user-123",
            "email": "pilot@test.com",
            "preferred_username": "pilot_01",
            "realm_access": {"roles": ["instructor", "org-admin"]},
            "organization_id": "org-uuid-456",
        }
        user = _extract_user_from_payload(payload)
        assert user.keycloak_id == "kc-user-123"
        assert user.email == "pilot@test.com"
        assert user.display_name == "pilot_01"
        assert user.roles == ["instructor", "org-admin"]
        assert user.organization_id == "org-uuid-456"

    def test_minimal_payload_uses_defaults(self) -> None:
        """Missing fields should use empty-string defaults."""
        payload: dict = {}
        user = _extract_user_from_payload(payload)
        assert user.keycloak_id == ""
        assert user.email == ""
        assert user.display_name == ""
        assert user.roles == []
        assert user.organization_id is None

    def test_name_fallback_when_no_preferred_username(self) -> None:
        """Falls back to 'name' when 'preferred_username' is absent."""
        payload = {
            "sub": "kc-1",
            "email": "a@b.com",
            "name": "Fallback Name",
        }
        user = _extract_user_from_payload(payload)
        assert user.display_name == "Fallback Name"

    def test_preferred_username_takes_priority_over_name(self) -> None:
        payload = {
            "sub": "kc-1",
            "email": "a@b.com",
            "preferred_username": "preferred",
            "name": "fallback",
        }
        user = _extract_user_from_payload(payload)
        assert user.display_name == "preferred"

    def test_no_realm_access_returns_empty_roles(self) -> None:
        payload = {"sub": "kc-1", "email": "a@b.com"}
        user = _extract_user_from_payload(payload)
        assert user.roles == []

    def test_realm_access_without_roles_key(self) -> None:
        payload = {"sub": "kc-1", "email": "a@b.com", "realm_access": {}}
        user = _extract_user_from_payload(payload)
        assert user.roles == []


# ── _decode_token ──────────────────────────────────────────────────────


class TestDecodeToken:
    """Tests for _decode_token() — mock JWKS and jose.jwt."""

    FAKE_JWKS = {
        "keys": [
            {"kid": "key-1", "kty": "RSA", "n": "abc", "e": "AQAB"},
        ]
    }

    @pytest.mark.asyncio
    @patch("app.middleware.auth._get_jwks")
    @patch("app.middleware.auth.jwt")
    @patch("app.middleware.auth.get_settings")
    async def test_valid_token(
        self, mock_settings: MagicMock, mock_jwt: MagicMock, mock_get_jwks: AsyncMock
    ) -> None:
        from app.middleware.auth import _decode_token

        settings = MagicMock()
        settings.keycloak_client_id = "horus-api"
        settings.keycloak_issuer_url = "http://localhost:8080/realms/horus"
        mock_settings.return_value = settings

        mock_get_jwks.return_value = self.FAKE_JWKS
        mock_jwt.get_unverified_header.return_value = {"kid": "key-1", "alg": "RS256"}
        mock_jwt.decode.return_value = {"sub": "user-1", "email": "u@e.com"}

        result = await _decode_token("valid.jwt.token")

        assert result == {"sub": "user-1", "email": "u@e.com"}
        mock_jwt.decode.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.middleware.auth._fetch_jwks")
    @patch("app.middleware.auth._get_jwks")
    @patch("app.middleware.auth.jwt")
    @patch("app.middleware.auth.get_settings")
    async def test_key_rotation_triggers_refresh(
        self,
        mock_settings: MagicMock,
        mock_jwt: MagicMock,
        mock_get_jwks: AsyncMock,
        mock_fetch_jwks: AsyncMock,
    ) -> None:
        """When kid not in cached JWKS, refresh should be attempted."""
        from app.middleware.auth import _decode_token

        settings = MagicMock()
        settings.keycloak_client_id = "horus-api"
        settings.keycloak_issuer_url = "http://localhost:8080/realms/horus"
        mock_settings.return_value = settings

        # Initial JWKS has no matching key
        mock_get_jwks.return_value = {"keys": [{"kid": "old-key"}]}
        # Refreshed JWKS has the matching key
        mock_fetch_jwks.return_value = {
            "keys": [{"kid": "new-key", "kty": "RSA", "n": "x", "e": "AQAB"}]
        }
        mock_jwt.get_unverified_header.return_value = {"kid": "new-key"}
        mock_jwt.decode.return_value = {"sub": "rotated-user"}

        result = await _decode_token("rotated.jwt.token")

        assert result["sub"] == "rotated-user"
        mock_fetch_jwks.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.middleware.auth._fetch_jwks")
    @patch("app.middleware.auth._get_jwks")
    @patch("app.middleware.auth.jwt")
    @patch("app.middleware.auth.get_settings")
    async def test_unknown_kid_after_refresh_raises_401(
        self,
        mock_settings: MagicMock,
        mock_jwt: MagicMock,
        mock_get_jwks: AsyncMock,
        mock_fetch_jwks: AsyncMock,
    ) -> None:
        from app.middleware.auth import _decode_token

        settings = MagicMock()
        settings.keycloak_client_id = "horus-api"
        settings.keycloak_issuer_url = "http://localhost:8080/realms/horus"
        mock_settings.return_value = settings

        mock_get_jwks.return_value = {"keys": []}
        mock_fetch_jwks.return_value = {"keys": []}
        mock_jwt.get_unverified_header.return_value = {"kid": "nonexistent"}

        with pytest.raises(HTTPException) as exc_info:
            await _decode_token("bad.jwt.token")
        assert exc_info.value.status_code == 401
        assert "Unable to find signing key" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.middleware.auth._get_jwks")
    @patch("app.middleware.auth.jwt")
    @patch("app.middleware.auth.get_settings")
    async def test_invalid_jwt_raises_401(
        self, mock_settings: MagicMock, mock_jwt: MagicMock, mock_get_jwks: AsyncMock
    ) -> None:
        from jose import JWTError

        from app.middleware.auth import _decode_token

        settings = MagicMock()
        settings.keycloak_client_id = "horus-api"
        settings.keycloak_issuer_url = "http://localhost:8080/realms/horus"
        mock_settings.return_value = settings

        mock_get_jwks.return_value = self.FAKE_JWKS
        mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
        mock_jwt.decode.side_effect = JWTError("Signature verification failed")
        mock_jwt.JWTError = JWTError

        with pytest.raises(HTTPException) as exc_info:
            await _decode_token("expired.jwt.token")
        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail


# ── get_current_user ───────────────────────────────────────────────────


class TestGetCurrentUser:
    """Tests for get_current_user() dependency."""

    @pytest.mark.asyncio
    @patch("app.middleware.auth.get_settings")
    async def test_auth_disabled_returns_dev_user(
        self, mock_settings: MagicMock
    ) -> None:
        settings = MagicMock()
        settings.auth_enabled = False
        mock_settings.return_value = settings

        request = MagicMock()
        user = await get_current_user(request)

        assert user.keycloak_id == "dev-user"
        assert user.email == "dev@horusone.app"
        assert user.display_name == "Dev User"
        assert "platform-admin" in user.roles

    @pytest.mark.asyncio
    @patch("app.middleware.auth._decode_token")
    @patch("app.middleware.auth.get_settings")
    async def test_auth_enabled_valid_token(
        self, mock_settings: MagicMock, mock_decode: AsyncMock
    ) -> None:
        settings = MagicMock()
        settings.auth_enabled = True
        mock_settings.return_value = settings

        mock_decode.return_value = {
            "sub": "kc-real-user",
            "email": "real@example.com",
            "preferred_username": "real_user",
            "realm_access": {"roles": ["instructor"]},
            "organization_id": "org-xyz",
        }

        request = MagicMock()
        request.headers.get.return_value = "Bearer valid.jwt.token"

        user = await get_current_user(request)

        assert user.keycloak_id == "kc-real-user"
        assert user.email == "real@example.com"
        assert user.roles == ["instructor"]
        assert user.organization_id == "org-xyz"

    @pytest.mark.asyncio
    @patch("app.middleware.auth.get_settings")
    async def test_auth_enabled_missing_header_raises_401(
        self, mock_settings: MagicMock
    ) -> None:
        settings = MagicMock()
        settings.auth_enabled = True
        mock_settings.return_value = settings

        request = MagicMock()
        request.headers.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401


# ── require_role ───────────────────────────────────────────────────────


class TestRequireRole:
    """Tests for the require_role() dependency factory."""

    @pytest.mark.asyncio
    async def test_user_has_required_role(self) -> None:
        checker = require_role("instructor")
        user = TokenUser(
            keycloak_id="kc-1",
            email="i@test.com",
            display_name="Instr",
            roles=["instructor", "org-admin"],
        )
        result = await checker(user)
        assert result is user

    @pytest.mark.asyncio
    async def test_user_missing_role_raises_403(self) -> None:
        checker = require_role("platform-admin")
        user = TokenUser(
            keycloak_id="kc-1",
            email="s@test.com",
            display_name="Student",
            roles=["student"],
        )
        with pytest.raises(HTTPException) as exc_info:
            await checker(user)
        assert exc_info.value.status_code == 403
        assert "platform-admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_multiple_allowed_roles_any_match(self) -> None:
        """If any of the allowed roles match, access is granted."""
        checker = require_role("platform-admin", "org-admin")
        user = TokenUser(
            keycloak_id="kc-1",
            email="a@test.com",
            display_name="Admin",
            roles=["org-admin"],
        )
        result = await checker(user)
        assert result is user

    @pytest.mark.asyncio
    async def test_empty_user_roles_raises_403(self) -> None:
        checker = require_role("instructor")
        user = TokenUser(
            keycloak_id="kc-1",
            email="e@test.com",
            display_name="Empty",
            roles=[],
        )
        with pytest.raises(HTTPException) as exc_info:
            await checker(user)
        assert exc_info.value.status_code == 403
