"""Guards for the Traefik edge middlewares (security headers, rate limit).

The middlewares live in ``docker/traefik/dynamic.yml`` and are loaded through the
file provider enabled in both compose files. They are baked into
``docker/Dockerfile.traefik`` rather than bind-mounted so the edge protection is
present regardless of host file semantics — a missing bind-mount path would
silently drop both middlewares. These tests keep the wiring from drifting away
from the middlewares it advertises.
"""

from __future__ import annotations

from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]

RELATIVE_DYNAMIC_CONFIG = "traefik/dynamic.yml"
DYNAMIC_CONFIG_PATH = "/etc/traefik/dynamic/dynamic.yml"
TRAEFIK_DOCKERFILE = "Dockerfile.traefik"
FILE_PROVIDER_FLAG = "--providers.file.directory=/etc/traefik/dynamic"
EDGE_MIDDLEWARES = ("security-headers@file", "rate-limit@file")


def _construct_override(loader: yaml.SafeLoader, node: yaml.Node) -> object:
    """Resolve Compose's ``!override`` tag the way Compose does (plain value)."""
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands Compose's ``!override`` extension tag."""


_ComposeLoader.add_constructor("!override", _construct_override)


def _compose(name: str = "docker-compose.yml") -> dict:
    text = (BACKEND_DIR / name).read_text()
    return yaml.load(text, Loader=_ComposeLoader)


def _dynamic() -> dict:
    return yaml.safe_load((BACKEND_DIR / "docker" / RELATIVE_DYNAMIC_CONFIG).read_text())


def test_dynamic_config_defines_the_edge_middlewares() -> None:
    assert set(_dynamic()["http"]["middlewares"]) == {"security-headers", "rate-limit"}


def test_security_headers_middleware_covers_the_expected_headers() -> None:
    headers = _dynamic()["http"]["middlewares"]["security-headers"]["headers"]
    assert headers["stsSeconds"] > 0
    assert headers["contentTypeNosniff"] is True
    assert headers["frameDeny"] is True
    assert headers["referrerPolicy"] == "no-referrer"
    assert headers["permissionsPolicy"]


def test_rate_limit_middleware_has_a_bounded_bucket() -> None:
    rate = _dynamic()["http"]["middlewares"]["rate-limit"]["rateLimit"]
    assert rate["average"] > 0
    assert rate["burst"] >= rate["average"]


def test_traefik_dockerfile_bakes_the_dynamic_config() -> None:
    dockerfile = (BACKEND_DIR / "docker" / TRAEFIK_DOCKERFILE).read_text()
    assert "FROM traefik:v3.1" in dockerfile
    assert f"COPY {RELATIVE_DYNAMIC_CONFIG} {DYNAMIC_CONFIG_PATH}" in dockerfile


def test_traefik_service_is_built_and_enables_the_file_provider() -> None:
    traefik = _compose()["services"]["traefik"]
    build = traefik.get("build") or {}
    assert build.get("context") == "./docker"
    assert build.get("dockerfile") == TRAEFIK_DOCKERFILE
    assert "image" not in traefik, (
        "traefik must be built, not pulled, so the baked middlewares cannot be "
        "shadowed by a stock image without the dynamic config"
    )
    assert FILE_PROVIDER_FLAG in traefik["command"]


def test_prod_overlay_also_enables_the_file_provider() -> None:
    command = _compose("docker-compose.prod.yml")["services"]["traefik"]["command"]
    assert FILE_PROVIDER_FLAG in command


def test_every_router_attaches_the_edge_middlewares() -> None:
    services = _compose()["services"]
    for router in ("backend", "keycloak"):
        labels = " ".join(services[router].get("labels", []) or [])
        for middleware in EDGE_MIDDLEWARES:
            assert middleware in labels, f"{router} router is missing {middleware}"
