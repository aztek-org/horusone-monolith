"""Guards that demo credentials are never committed (issue #70).

The realm JSON is baked into the Keycloak image, so any literal password in it
is public. Passwords must be env placeholders AND the compose file must force
those variables to be set: Keycloak substitutes ``${VAR}`` at import time, but
an *unset* variable is left literal (``${DEMO_USER_PASSWORD}`` becomes the
password — a login bypass) and an *empty* one crashes the server at startup.
Hence ``${VAR:?message}``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_DIR.parent
REALM = BACKEND_DIR / "docker" / "keycloak-import" / "horus-realm.json"

_PLACEHOLDER = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_LEAKED_PASSWORDS = ("@dmin2026", "stud3nt2026")


def _realm() -> dict:
    return json.loads(REALM.read_text())


def _keycloak_env() -> dict:
    compose = yaml.safe_load((BACKEND_DIR / "docker-compose.yml").read_text())
    return compose["services"]["keycloak"]["environment"]


def _credential_placeholder_vars() -> set[str]:
    names: set[str] = set()
    for user in _realm().get("users", []):
        for cred in user.get("credentials", []):
            if cred.get("type") != "password":
                continue
            match = _PLACEHOLDER.match(cred.get("value", ""))
            assert match, (
                f"credential for {user.get('username')!r} is not an env "
                f"placeholder: {cred.get('value')!r}"
            )
            names.add(match.group(1))
    return names


def test_realm_passwords_are_env_placeholders() -> None:
    placeholders = _credential_placeholder_vars()
    assert placeholders, "expected at least one demo credential"
    assert {"DEMO_ADMIN_PASSWORD", "DEMO_USER_PASSWORD"} <= placeholders


def test_compose_provides_every_realm_placeholder() -> None:
    env = _keycloak_env()
    missing = _credential_placeholder_vars() - set(env)
    assert not missing, (
        f"docker-compose.yml keycloak service does not provide {missing}; "
        "Keycloak would store the literal placeholder as the password"
    )


def test_compose_forces_the_demo_passwords_to_be_set() -> None:
    env = _keycloak_env()
    for var in _credential_placeholder_vars():
        assert ":?" in str(env[var]), (
            f"{var} must be interpolated as ${{{var}:?message}} so an unset or "
            "empty value cannot fall back to a literal password"
        )


def test_env_templates_document_the_demo_password_vars() -> None:
    for name in (".env.example", ".env.docker.example", ".env.prod.example"):
        text = (BACKEND_DIR / name).read_text()
        for var in ("DEMO_ADMIN_PASSWORD", "DEMO_USER_PASSWORD"):
            assert var in text, f"{name} must document {var}"


def test_docs_do_not_leak_the_demo_passwords() -> None:
    for rel in ("CREDS.md", "README.md"):
        text = (REPO_ROOT / rel).read_text()
        for literal in _LEAKED_PASSWORDS:
            assert literal not in text, f"{rel} still contains {literal!r}"
