"""Guards for Postgres first-boot initialization (``keycloak_db``).

On a fresh volume the ``pgvector/pgvector:pg16`` entrypoint runs everything in
``/docker-entrypoint-initdb.d`` exactly once. That init script must therefore be
*guaranteed* present and executable **inside the image**, independent of the
host filesystem's permission bits (a host bind mount loses the exec bit on
SELinux, macOS/Windows mounts, and can even be materialised as a directory).

We bake it into a small image (``docker/Dockerfile.postgres``) instead of
bind-mounting it. These tests keep that invariant from silently regressing.
"""

from __future__ import annotations

from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_DIR.parent

INIT_SCRIPT_NAME = "init-multiple-dbs.sh"
INITDB_PATH = "/docker-entrypoint-initdb.d/init-multiple-dbs.sh"
POSTGRES_DOCKERFILE = "Dockerfile.postgres"


def _compose(name: str = "docker-compose.yml") -> dict:
    return yaml.safe_load((BACKEND_DIR / name).read_text())


def _postgres_service() -> dict:
    return _compose()["services"]["postgres"]


def _init_script() -> str:
    return (BACKEND_DIR / "docker" / INIT_SCRIPT_NAME).read_text()


def test_postgres_bakes_init_script_via_a_build() -> None:
    build = _postgres_service().get("build")
    assert build, "postgres must build a local image with the init script baked in"
    assert build["context"] == "./docker"
    assert build["dockerfile"] == POSTGRES_DOCKERFILE


def test_postgres_does_not_bind_mount_the_init_script() -> None:
    volumes = _postgres_service().get("volumes", []) or []
    assert not any(INIT_SCRIPT_NAME in str(v) for v in volumes), (
        "the init script must not depend on a host bind mount: exec-bit, SELinux "
        "and CRLF handling all differ per host, and the source of truth is now "
        "the built image"
    )


def test_postgres_dockerfile_copies_and_marks_the_init_script_executable() -> None:
    dockerfile = (BACKEND_DIR / "docker" / POSTGRES_DOCKERFILE).read_text()
    assert "FROM pgvector/pgvector:pg16" in dockerfile
    assert f"COPY {INIT_SCRIPT_NAME} {INITDB_PATH}" in dockerfile
    assert f"chmod +x {INITDB_PATH}" in dockerfile


def test_init_script_creates_the_keycloak_database() -> None:
    script = _init_script()
    assert script.startswith("#!/bin/bash")
    assert "set -e" in script
    assert "set -u" in script
    assert "CREATE USER keycloak" in script
    assert "CREATE DATABASE keycloak_db" in script


def test_gitattributes_forces_lf_for_shell_scripts() -> None:
    attrs = (REPO_ROOT / ".gitattributes").read_text().splitlines()
    rules = [line.strip() for line in attrs if line.strip() and not line.startswith("#")]
    assert any(
        rule.startswith("*.sh") and "eol=lf" in rule and "-text" not in rule
        for rule in rules
    ), "*.sh must be checked out with LF endings or Windows builds bake CRLF into the init script"
