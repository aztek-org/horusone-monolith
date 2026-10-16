"""Unit tests for deterministic organization id helpers."""

from __future__ import annotations

import uuid

from app.core.org_ids import org_id_for_slug, parse_org_id_claim


class TestOrgIdForSlug:
    def test_matches_namespace_dns_convention(self) -> None:
        assert org_id_for_slug("skybridge") == uuid.uuid5(uuid.NAMESPACE_DNS, "skybridge.aero")

    def test_is_deterministic(self) -> None:
        assert org_id_for_slug("acme") == org_id_for_slug("acme")

    def test_differs_by_slug(self) -> None:
        assert org_id_for_slug("alpha") != org_id_for_slug("bravo")


class TestParseOrgIdClaim:
    def test_uuid_string_passthrough(self) -> None:
        org = uuid.uuid4()
        assert parse_org_id_claim(str(org)) == org

    def test_slug_resolved_to_uuid(self) -> None:
        assert parse_org_id_claim("skybridge") == org_id_for_slug("skybridge")

    def test_empty_string_returns_none(self) -> None:
        assert parse_org_id_claim("") is None

    def test_none_returns_none(self) -> None:
        assert parse_org_id_claim(None) is None
