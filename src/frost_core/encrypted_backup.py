from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class EncryptedBackupError(RuntimeError):
    """Encrypted backup creation or recovery failed closed."""


_AGE_RECIPIENT = re.compile(r"^age1[023456789acdefghjklmnpqrstuvwxyz]{20,}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_age(age_binary: str) -> str:
    candidate = shutil.which(age_binary)
    if candidate is None:
        raise EncryptedBackupError(
            "age encryption provider is unavailable; plaintext fallback is forbidden"
        )
    return candidate


def encrypt_backup(
    source: str | Path,
    output: str | Path,
    *,
    recipient: str,
    age_binary: str = "age",
    target_ref: str = "",
) -> dict[str, Any]:
    """Encrypt one backup through the external `age` provider with no shell.

    This function establishes encrypted artifact creation. It does not claim that the
    destination is physically off-device; external replication remains a separate
    connector/evidence gate represented by ``off_device_replication_verified=false``.
    """

    source_path = Path(source)
    if not source_path.is_file() or source_path.is_symlink():
        raise EncryptedBackupError("backup source must be a regular non-symlink file")
    recipient = recipient.strip()
    if not _AGE_RECIPIENT.fullmatch(recipient):
        raise EncryptedBackupError("recipient must be a native age public recipient")
    age = _resolve_age(age_binary)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            [age, "--encrypt", "--recipient", recipient, "--output", str(temporary), str(source_path)],
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise EncryptedBackupError(f"age encryption failed: {detail}")
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise EncryptedBackupError("age returned success without ciphertext")
        os.chmod(temporary, 0o600)
        temporary.replace(output_path)
    except subprocess.TimeoutExpired as exc:
        raise EncryptedBackupError("age encryption timed out") from exc
    finally:
        temporary.unlink(missing_ok=True)

    receipt = {
        "schema": "frost.encrypted_backup.receipt.v1",
        "provider": "age",
        "source_sha256": _sha256(source_path),
        "ciphertext_sha256": _sha256(output_path),
        "ciphertext_size_bytes": output_path.stat().st_size,
        "target_ref": target_ref,
        "encrypted_artifact_verified_present": True,
        "off_device_replication_verified": False,
        "plaintext_fallback_allowed": False,
    }
    receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(receipt_path, 0o600)
    return receipt


def rotation_plan(directory: str | Path, *, keep: int) -> dict[str, Any]:
    """Return deletion candidates without deleting encrypted evidence."""

    if keep < 1:
        raise ValueError("keep must be >= 1")
    root = Path(directory)
    if not root.is_dir():
        raise EncryptedBackupError("backup rotation directory does not exist")
    backups = sorted(
        (path for path in root.glob("*.age") if path.is_file() and not path.is_symlink()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    return {
        "keep": [path.name for path in backups[:keep]],
        "deletion_candidates": [path.name for path in backups[keep:]],
        "deletion_authorized": False,
    }
