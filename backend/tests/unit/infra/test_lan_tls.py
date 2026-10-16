"""Guards for the LAN / self-hosted HTTPS overlay (#73).

Browsers only expose ``crypto.subtle`` (PKCE sign-in) and
``navigator.mediaDevices`` (voice) in a secure context. Serving Horus over plain
HTTP on a LAN address breaks both, so ``docker-compose.lan.yml`` terminates TLS
with a locally-trusted certificate from ``scripts/gen-lan-certs.sh`` (mkcert)
instead of ACME, and routes the API/auth/frontend over HTTPS. These tests keep
the overlay, the dynamic TLS store and the cert script from drifting apart.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[3]

LAN_COMPOSE = "docker-compose.lan.yml"
LAN_DYNAMIC = "docker/traefik/dynamic-lan.yml"
CERT_SCRIPT = "scripts/gen-lan-certs.sh"


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


def _compose(name: str) -> dict:
    return yaml.load((BACKEND_DIR / name).read_text(), Loader=_ComposeLoader)


def _lan_dynamic() -> dict:
    return yaml.safe_load((BACKEND_DIR / LAN_DYNAMIC).read_text())


def _volumes(service: dict) -> str:
    return " ".join(v for v in service.get("volumes", []) if isinstance(v, str))


def test_lan_overlay_terminates_tls_locally_instead_of_acme() -> None:
    command = " ".join(_compose(LAN_COMPOSE)["services"]["traefik"]["command"])
    assert "--entrypoints.websecure.address=:443" in command
    assert "redirections.entryPoint.to=websecure" in command
    assert "certificatesresolvers" not in command, (
        "the LAN stack uses the local mkcert certificate, not ACME"
    )


def test_lan_overlay_mounts_the_certificate_and_dynamic_config() -> None:
    volumes = _volumes(_compose(LAN_COMPOSE)["services"]["traefik"])
    assert "./docker/certs:/certs:ro" in volumes
    assert f"./{LAN_DYNAMIC}:/etc/traefik/dynamic/lan.yml:ro" in volumes


def test_default_certificate_points_at_the_generated_files() -> None:
    cert = _lan_dynamic()["tls"]["stores"]["default"]["defaultCertificate"]
    assert cert["certFile"] == "/certs/lan.crt"
    assert cert["keyFile"] == "/certs/lan.key"


def test_api_and_auth_routers_are_served_over_https() -> None:
    services = _compose(LAN_COMPOSE)["services"]
    for service, prefix in (("backend", "api"), ("keycloak", "auth")):
        labels = " ".join(services[service]["labels"])
        assert f"Host(`{prefix}.${{LAN_HOSTNAME:-horus.lan}}`)" in labels
        assert "entrypoints=websecure" in labels
        assert "tls=true" in labels


def test_backend_issuer_and_keycloak_hostname_follow_the_lan_hostname() -> None:
    services = _compose(LAN_COMPOSE)["services"]
    assert (
        services["backend"]["environment"]["KEYCLOAK_ISSUER_URL"]
        == "https://auth.${LAN_HOSTNAME:-horus.lan}/realms/horus"
    )
    assert services["keycloak"]["environment"]["KC_HOSTNAME"] == ("auth.${LAN_HOSTNAME:-horus.lan}")


def test_cert_script_mints_the_files_the_store_expects() -> None:
    script = (BACKEND_DIR / CERT_SCRIPT).read_text()
    assert "lan.crt" in script
    assert "lan.key" in script
    assert "mkcert" in script
    # The router/store default host must be among the generated SANs so the
    # browser accepts the certificate for it.
    assert "app.${HOST}" in script
    assert "api.${HOST}" in script
    assert "auth.${HOST}" in script


def test_cert_script_fails_loudly_without_mkcert(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    dirname = shutil.which("dirname")
    assert bash is not None and dirname is not None

    # Minimal PATH: enough for the script's own `dirname` call, but deliberately
    # without mkcert, so the failure path is exercised.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "dirname").symlink_to(dirname)

    completed = subprocess.run(
        [bash, str(BACKEND_DIR / CERT_SCRIPT)],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": str(bin_dir)},
    )
    assert completed.returncode != 0
    assert "mkcert" in completed.stderr
