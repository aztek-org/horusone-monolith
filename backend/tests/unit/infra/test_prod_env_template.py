"""Guards that the production env template is complete and actually consumed.

``docker compose -f docker-compose.yml -f docker-compose.prod.yml`` interpolates
several variables from the environment (``--env-file``). If the template omits
any of them the stack silently starts with empty secrets (whole postgres/redis/
keycloak passwords, TLS hostnames). See issue #69.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_DIR.parent

COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.dev.yml",
)
TEMPLATE = ".env.prod.example"

# ${VAR} / ${VAR:-default} / ${VAR:?err} — capture the name.
_INTERPOLATION = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[-?][^}]*)?\}")

# The secrets/hostnames the production stack cannot function without.
REQUIRED_PROD_KEYS = frozenset(
    {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "KEYCLOAK_ADMIN_PASSWORD",
        "KEYCLOAK_DB_PASSWORD",
        "ACME_EMAIL",
        "API_HOSTNAME",
        "KEYCLOAK_HOSTNAME",
    }
)


def _compose_interpolation_vars() -> set[str]:
    names: set[str] = set()
    for name in COMPOSE_FILES:
        names |= set(_INTERPOLATION.findall((BACKEND_DIR / name).read_text()))
    return names


def _template_keys() -> set[str]:
    keys: set[str] = set()
    for line in (BACKEND_DIR / TEMPLATE).read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def test_template_documents_every_compose_interpolation_var() -> None:
    missing = sorted(_compose_interpolation_vars() - _template_keys())
    assert not missing, (
        f"{TEMPLATE} does not document the compose interpolation variables "
        f"{missing}; the production stack would start with empty values"
    )


def test_template_includes_the_required_prod_secrets() -> None:
    missing = sorted(REQUIRED_PROD_KEYS - _template_keys())
    assert not missing, f"{TEMPLATE} is missing required secrets: {missing}"


def test_deploy_script_loads_the_prod_env_file() -> None:
    script = (BACKEND_DIR / "scripts" / "deploy.sh").read_text()
    assert "--env-file .env.prod" in script, (
        "deploy.sh must pass --env-file .env.prod or compose interpolation runs "
        "with empty secrets"
    )


def test_env_templates_are_not_gitignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text().splitlines()
    negations = {
        line.strip()[1:]
        for line in gitignore
        if line.strip().startswith("!")
    }
    for template in (TEMPLATE, ".env.example", ".env.docker.example"):
        assert template in negations, (
            f".gitignore must explicitly un-ignore {template} (a typo'd "
            "negation silently drops the template from the repo)"
        )
