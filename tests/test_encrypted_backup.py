from __future__ import annotations

import os

import pytest

from frost_core.encrypted_backup import (
    EncryptedBackupError,
    encrypt_backup,
    rotation_plan,
)


RECIPIENT = "age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"


def fake_age(tmp_path):
    path = tmp_path / "age"
    path.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index('--output') + 1])
source = pathlib.Path(args[-1])
out.write_bytes(b'AGE-FAKE-CIPHERTEXT\\n' + source.read_bytes()[::-1])
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o700)
    return path


def test_backup_requires_real_provider_path_and_never_falls_back_to_plaintext(tmp_path) -> None:
    source = tmp_path / "backup.zip"
    source.write_bytes(b"canonical backup")
    with pytest.raises(EncryptedBackupError, match="plaintext fallback is forbidden"):
        encrypt_backup(
            source,
            tmp_path / "backup.age",
            recipient=RECIPIENT,
            age_binary="definitely-not-installed-age-provider",
        )
    assert not (tmp_path / "backup.age").exists()


def test_backup_delegates_to_age_and_records_nonpromotion_of_off_device_state(tmp_path) -> None:
    source = tmp_path / "backup.zip"
    source.write_bytes(b"canonical backup")
    provider = fake_age(tmp_path)
    output = tmp_path / "backup.age"
    receipt = encrypt_backup(
        source,
        output,
        recipient=RECIPIENT,
        age_binary=str(provider),
        target_ref="drive://automation-backups",
    )
    assert output.read_bytes().startswith(b"AGE-FAKE-CIPHERTEXT")
    assert receipt["provider"] == "age"
    assert receipt["encrypted_artifact_verified_present"] is True
    assert receipt["off_device_replication_verified"] is False
    assert receipt["plaintext_fallback_allowed"] is False
    assert output.with_suffix(".age.receipt.json").exists()


def test_recipient_input_cannot_be_used_as_shell_or_option_injection(tmp_path) -> None:
    source = tmp_path / "backup.zip"
    source.write_bytes(b"canonical backup")
    provider = fake_age(tmp_path)
    with pytest.raises(EncryptedBackupError, match="native age public recipient"):
        encrypt_backup(
            source,
            tmp_path / "backup.age",
            recipient="$(touch /tmp/should-not-run)",
            age_binary=str(provider),
        )


def test_symlink_source_is_rejected(tmp_path) -> None:
    source = tmp_path / "backup.zip"
    source.write_bytes(b"canonical backup")
    link = tmp_path / "linked.zip"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(EncryptedBackupError, match="non-symlink"):
        encrypt_backup(
            link,
            tmp_path / "backup.age",
            recipient=RECIPIENT,
            age_binary=str(fake_age(tmp_path)),
        )


def test_rotation_is_plan_only_and_never_deletes_evidence(tmp_path) -> None:
    for index in range(4):
        path = tmp_path / f"backup-{index}.age"
        path.write_bytes(str(index).encode())
        os.utime(path, ns=(index + 1, index + 1))
    plan = rotation_plan(tmp_path, keep=2)
    assert len(plan["keep"]) == 2
    assert len(plan["deletion_candidates"]) == 2
    assert plan["deletion_authorized"] is False
    assert len(list(tmp_path.glob("*.age"))) == 4
