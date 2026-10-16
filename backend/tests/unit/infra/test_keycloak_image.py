"""Guards for the Keycloak image and realm import.

Keycloak imports its realm from ``/opt/keycloak/data/import`` via
``--import-realm``. That directory used to be a host bind mount — the same
fragility fixed for Postgres in #20 — and there was a second, stale copy of the
realm JSON (#68). The realm is now baked into a small image, and exactly one
copy of the realm file exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]
KEYCLOAK_REALM = "horus-realm.json"
REALM_CONTAINER_PATH = "/opt/keycloak/data/import/horus-realm.json"
KEYCLOAK_DOCKERFILE = "Dockerfile.keycloak"


def _compose(name: str = "docker-compose.yml") -> dict:
    return yaml.safe_load((BACKEND_DIR / name).read_text())


def _keycloak_service() -> dict:
    return _compose()["services"]["keycloak"]


def test_keycloak_bakes_realm_via_a_build() -> None:
    build = _keycloak_service().get("build")
    assert build, "keycloak must build a local image with the realm baked in"
    assert build["context"] == "./docker"
    assert build["dockerfile"] == KEYCLOAK_DOCKERFILE


def test_keycloak_does_not_bind_mount_the_realm() -> None:
    volumes = _keycloak_service().get("volumes", []) or []
    assert not any("keycloak-import" in str(v) for v in volumes), (
        "the realm must not be host bind-mounted: the source of truth is the "
        "built image"
    )


def test_keycloak_dockerfile_bakes_the_realm() -> None:
    dockerfile = (BACKEND_DIR / "docker" / KEYCLOAK_DOCKERFILE).read_text()
    assert "FROM quay.io/keycloak/keycloak:24.0" in dockerfile
    assert f"COPY keycloak-import/{KEYCLOAK_REALM} {REALM_CONTAINER_PATH}" in dockerfile


def test_exactly_one_realm_file_is_tracked() -> None:
    realm_files = sorted((BACKEND_DIR / "docker").rglob(KEYCLOAK_REALM))
    expected = [BACKEND_DIR / "docker" / "keycloak-import" / KEYCLOAK_REALM]
    assert realm_files == expected, (
        "the stale duplicate realm JSON must be gone so there is a single "
        "source of truth"
    )


def test_baked_realm_is_valid_and_named_horus() -> None:
    realm = json.loads(
        (BACKEND_DIR / "docker" / "keycloak-import" / KEYCLOAK_REALM).read_text()
    )
    assert realm["realm"] == "horus"
