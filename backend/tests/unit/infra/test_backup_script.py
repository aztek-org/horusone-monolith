"""Behavioural guards for ``scripts/backup.sh`` (#72).

Backups must be encrypted with age before they touch disk, and the script must
fail closed when it cannot encrypt — a misconfigured host must never leave
plaintext database credentials lying around. Offsite upload is optional, but
must only ever happen when a remote is configured.

The script is executed in a sandbox with ``docker``/``age``/``rclone`` stubbed
on ``PATH``, so we assert on real pipeline behaviour rather than on prose.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
BACKUP_SCRIPT = BACKEND_DIR / "scripts" / "backup.sh"

_RECIPIENT = "age1qyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqs3xxxx"

_STUB_DOCKER = """\
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "compose" && "${2:-}" == "ps" ]]; then
  echo "running"
  exit 0
fi
if [[ "${1:-}" == "compose" && "${2:-}" == "exec" ]]; then
  echo "-- fake pg_dump payload"
  exit 0
fi
exit 0
"""

_STUB_AGE = """\
#!/usr/bin/env bash
set -euo pipefail
cat
"""

_STUB_RCLONE = """\
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "${RCLONE_LOG:?RCLONE_LOG must be set}"
exit 0
"""


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_backup(
    tmp_path: Path,
    *,
    args: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    sandbox = tmp_path / "sandbox"
    scripts = sandbox / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(BACKUP_SCRIPT, scripts / "backup.sh")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_stub(bin_dir / "docker", _STUB_DOCKER)
    _write_stub(bin_dir / "age", _STUB_AGE)
    _write_stub(bin_dir / "rclone", _STUB_RCLONE)

    rclone_log = tmp_path / "rclone.log"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BACKUP_", "RCLONE_"))
    }
    child_env["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
    child_env["RCLONE_LOG"] = str(rclone_log)
    child_env.update(env or {})

    completed = subprocess.run(
        ["bash", str(scripts / "backup.sh"), *args],
        cwd=sandbox,
        env=child_env,
        capture_output=True,
        text=True,
    )
    return completed, sandbox / "backups", rclone_log


def _dumps(backups: Path) -> list[str]:
    return sorted(
        path.name
        for path in backups.glob("*.sql.gz*")
        if path.is_file() and not path.name.endswith(".sha256")
    )


def test_missing_recipient_fails_closed(tmp_path: Path) -> None:
    completed, backups, _ = _run_backup(tmp_path)
    assert completed.returncode != 0
    assert "BACKUP_AGE_RECIPIENT" in completed.stderr
    assert _dumps(backups) == [], "no dump may be written when encryption is required"


def test_encrypts_every_dump_and_writes_checksums(tmp_path: Path) -> None:
    completed, backups, _ = _run_backup(tmp_path, env={"BACKUP_AGE_RECIPIENT": _RECIPIENT})
    assert completed.returncode == 0, completed.stderr

    dumps = _dumps(backups)
    assert all(name.endswith(".sql.gz.age") for name in dumps)
    assert not [name for name in dumps if name.endswith(".sql.gz")], (
        "a plaintext dump leaked to disk"
    )
    assert len(dumps) == 2, dumps  # horus_db + keycloak_db
    assert len(list(backups.glob("*.sql.gz.age.sha256"))) == 2


def test_no_encrypt_writes_plaintext(tmp_path: Path) -> None:
    completed, backups, _ = _run_backup(tmp_path, args=("--no-encrypt",))
    assert completed.returncode == 0, completed.stderr

    dumps = _dumps(backups)
    assert dumps, "expected plaintext dumps"
    assert all(name.endswith(".sql.gz") for name in dumps)
    assert not list(backups.glob("*.age"))


def test_single_database_selection(tmp_path: Path) -> None:
    completed, backups, _ = _run_backup(
        tmp_path,
        args=("--db", "horus_db"),
        env={"BACKUP_AGE_RECIPIENT": _RECIPIENT},
    )
    assert completed.returncode == 0, completed.stderr

    dumps = _dumps(backups)
    assert [name for name in dumps if name.startswith("horus_db")]
    assert not [name for name in dumps if name.startswith("keycloak_db")]


def test_no_upload_without_remote(tmp_path: Path) -> None:
    completed, _, rclone_log = _run_backup(tmp_path, env={"BACKUP_AGE_RECIPIENT": _RECIPIENT})
    assert completed.returncode == 0, completed.stderr
    assert not rclone_log.exists(), "rclone must not run without a configured remote"


def test_uploads_and_prunes_when_remote_configured(tmp_path: Path) -> None:
    completed, _, rclone_log = _run_backup(
        tmp_path,
        env={
            "BACKUP_AGE_RECIPIENT": _RECIPIENT,
            "BACKUP_RCLONE_REMOTE": "horus-backups:horus-db",
        },
    )
    assert completed.returncode == 0, completed.stderr

    log = rclone_log.read_text()
    assert "copyto" in log
    assert "horus-backups:horus-db" in log
    assert "check" in log
    assert "delete --min-age" in log
    assert "30d" in log


def test_require_offsite_without_remote_fails(tmp_path: Path) -> None:
    completed, backups, _ = _run_backup(
        tmp_path,
        args=("--require-offsite",),
        env={"BACKUP_AGE_RECIPIENT": _RECIPIENT},
    )
    assert completed.returncode != 0
    assert "offsite" in completed.stderr.lower()
    assert _dumps(backups) == []
