"""Regression tests for the Keycloak realm import (#18).

The ``organization_id`` user attribute is copied verbatim into the JWT claim
by the ``oidc-usermodel-attribute-mapper``.  It must hold the organization
**UUID**, not the slug, otherwise org-scoped endpoints raise ``uuid_parsing``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.core.org_ids import org_id_for_slug

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
REALM_FILES = [
    _BACKEND_ROOT / "docker" / "keycloak-import" / "horus-realm.json",
    _BACKEND_ROOT / "docker" / "keycloak" / "horus-realm.json",
]


def _realm_ids() -> list[str]:
    return [str(p.parent.name) for p in REALM_FILES]


def _organization_id_values(realm_path: Path) -> list[str]:
    realm = json.loads(realm_path.read_text(encoding="utf-8"))
    values: list[str] = []
    for user in realm.get("users", []):
        attrs = user.get("attributes") or {}
        for value in attrs.get("organization_id") or []:
            values.append(value)
    return values


@pytest.mark.parametrize("realm_path", REALM_FILES, ids=_realm_ids())
def test_realm_files_exist(realm_path: Path) -> None:
    assert realm_path.is_file()


@pytest.mark.parametrize("realm_path", REALM_FILES, ids=_realm_ids())
def test_organization_id_attribute_is_a_uuid(realm_path: Path) -> None:
    values = _organization_id_values(realm_path)
    assert values, "expected at least one user with an organization_id attribute"
    for value in values:
        uuid.UUID(value)  # raises if the claim still carries a slug


@pytest.mark.parametrize("realm_path", REALM_FILES, ids=_realm_ids())
def test_skybridge_users_use_seeded_org_uuid(realm_path: Path) -> None:
    expected = str(org_id_for_slug("skybridge"))
    values = _organization_id_values(realm_path)
    assert values
    assert all(value == expected for value in values)
