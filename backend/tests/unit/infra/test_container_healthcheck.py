"""Infra config guards: the backend health probe must only use what the runtime
image actually ships.

The runtime image (``docker/Dockerfile``, ``python:3.11-slim``) installs ffmpeg
and libsndfile1 but not curl. Its own ``HEALTHCHECK`` already probes ``/health``
with the Python standard library, so ``docker-compose.yml`` and
``scripts/deploy.sh`` must use that same probe — otherwise Compose reports the
container unhealthy forever and the deploy health gate times out (#19).
"""

from __future__ import annotations

from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]

# The probe the runtime image can run with nothing extra: the Python stdlib,
# already on PATH via the image's virtualenv.
HEALTH_PROBE_SNIPPET = (
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
)


def _compose(name: str = "docker-compose.yml") -> dict:
    return yaml.safe_load((BACKEND_DIR / name).read_text())


def _backend_healthcheck_test() -> str:
    test = _compose()["services"]["backend"]["healthcheck"]["test"]
    return " ".join(test) if isinstance(test, list) else str(test)


def _dockerfile() -> str:
    return (BACKEND_DIR / "docker" / "Dockerfile").read_text()


def _deploy_script() -> str:
    """The deploy script with comment lines stripped, so assertions target the
    commands it actually runs rather than prose about them."""
    text = (BACKEND_DIR / "scripts" / "deploy.sh").read_text()
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_backend_healthcheck_avoids_curl() -> None:
    probe = _backend_healthcheck_test()
    assert "curl" not in probe, (
        "the backend runtime image does not install curl; probing with it keeps "
        "the container unhealthy forever"
    )


def test_backend_healthcheck_uses_stdlib_probe() -> None:
    assert HEALTH_PROBE_SNIPPET in _backend_healthcheck_test()


def test_dockerfile_healthcheck_uses_stdlib_probe() -> None:
    dockerfile = _dockerfile()
    assert "curl" not in dockerfile
    assert HEALTH_PROBE_SNIPPET in dockerfile


def test_deploy_health_gate_uses_stdlib_probe() -> None:
    script = _deploy_script()
    assert "curl" not in script, (
        "deploy.sh probes the backend inside the container, where curl is absent"
    )
    assert HEALTH_PROBE_SNIPPET in script


def test_compose_and_deploy_probes_are_consistent() -> None:
    assert HEALTH_PROBE_SNIPPET in _backend_healthcheck_test()
    assert HEALTH_PROBE_SNIPPET in _deploy_script()
