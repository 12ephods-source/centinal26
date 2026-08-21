from __future__ import annotations

import json
from pathlib import Path

import pytest

from automation.device import evidence_gate_collector as gate


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_reboot_evaluation_requires_changed_boot_identity() -> None:
    pre = {"boot_id": "boot-a"}
    same = gate.reboot_evaluation(pre, "boot-a")
    changed = gate.reboot_evaluation(pre, "boot-b")
    assert same["boot_id_changed"] is False
    assert changed == {
        "pre_boot_id": "boot-a",
        "post_boot_id": "boot-b",
        "boot_id_changed": True,
    }


def test_status_never_promotes_without_required_observed_evidence(tmp_path: Path) -> None:
    dump(
        tmp_path / "current_commissioning.json",
        {
            "verification": {
                "status": "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE"
            }
        },
    )
    status = gate.synthesize_status(tmp_path)
    assert status["commissioning_eligible"] is True
    assert status["device_validated_eligible"] is False
    assert status["persistent_validated_eligible"] is False
    assert status["promotion_performed"] is False
    assert status["independent_judge_verified"] is False
    assert status["lease_event_chain_verified"] is False


def test_status_requires_real_roundtrip_and_post_reboot_work(tmp_path: Path) -> None:
    dump(
        tmp_path / "current_commissioning.json",
        {
            "verification": {
                "status": "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE"
            }
        },
    )
    dump(
        tmp_path / "worker_once_receipt.json",
        {"bounded_work_observed": True},
    )
    dump(
        tmp_path / "offdevice_roundtrip_receipt.json",
        {
            "encrypted_artifact_verified": True,
            "off_device_roundtrip_verified": True,
            "recovery_verified": True,
        },
    )
    dump(
        tmp_path / "post_reboot_receipt.json",
        {
            "boot_id_changed": True,
            "worker_return_observed": True,
            "post_reboot_bounded_work": {"bounded_work_observed": True},
        },
    )
    status = gate.synthesize_status(tmp_path)
    assert status["device_validated_eligible"] is True
    assert status["offdevice_recovery_verified"] is True
    assert status["reboot_return_and_work_observed"] is True
    assert status["persistent_validated_eligible"] is True
    assert status["promotion_performed"] is False


def test_make_zip_rejects_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "record.txt").write_text("evidence", encoding="utf-8")
    link = source / "linked.txt"
    try:
        link.symlink_to(source / "record.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(gate.EvidenceGateError, match="symlink rejected"):
        gate.make_zip(source, tmp_path / "bundle.zip")


def test_write_json_is_atomic_and_object_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    gate.write_json(path, {"status": "PASS"})
    assert gate.read_json(path) == {"status": "PASS"}
    assert not path.with_suffix(".json.tmp").exists()
