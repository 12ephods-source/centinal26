import json
from pathlib import Path

import pytest

from centinal26 import device_campaign as dc


def _physical_identity() -> dict:
    return {
        "python": "3.13.0",
        "implementation": "CPython",
        "system": "Linux",
        "release": "android-test",
        "machine": "aarch64",
        "termux": True,
        "android": True,
        "physical_device_inferred": True,
    }


def _prepare(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign"
    hook = tmp_path / "centinal26.sh"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(dc, "platform_identity", _physical_identity)
    monkeypatch.setattr(dc, "_read_boot_id", lambda: "boot-before")
    prepared = dc.prepare_device_campaign(campaign, boot_hook=hook)
    return campaign, hook, prepared


def test_device_campaign_requires_physical_termux(tmp_path, monkeypatch):
    hook = tmp_path / "centinal26.sh"
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        dc,
        "platform_identity",
        lambda: {
            "termux": False,
            "android": False,
            "physical_device_inferred": False,
        },
    )

    with pytest.raises(dc.DeviceCampaignError, match="physical Android Termux"):
        dc.prepare_device_campaign(tmp_path / "campaign", boot_hook=hook)


def test_campaign_fails_closed_until_real_reboot_then_verifies(tmp_path, monkeypatch):
    campaign, hook, prepared = _prepare(tmp_path, monkeypatch)
    assert prepared["decision"] == dc.DECISION_WAITING_FOR_REBOOT
    assert prepared["phase"] == dc.PHASE_AWAITING_REBOOT
    assert prepared["device_validated"] is True
    assert prepared["persistent_validated"] is False

    same_boot = dc.resume_device_campaign(campaign, boot_hook=hook)
    assert same_boot["decision"] == dc.DECISION_WAITING_FOR_REBOOT
    assert not (campaign / dc.REPORT_NAME).exists()

    monkeypatch.setattr(dc, "_read_boot_id", lambda: "boot-after")
    report = dc.resume_device_campaign(campaign, boot_hook=hook)

    assert report["decision"] == dc.DECISION_PERSISTENT_VALIDATED
    assert report["phase"] == dc.PHASE_COMPLETE
    assert report["promotion_scope"] == "PERSISTENT_VALIDATED"
    assert report["device_validated"] is True
    assert report["persistent_validated"] is True
    assert report["autonomous_validated"] is False
    assert report["pre_boot_id"] == "boot-before"
    assert report["post_boot_id"] == "boot-after"
    assert report["boot_id_changed"] is True
    assert report["pre_reboot_probe"]["task_status"] == "COMPLETE"
    assert report["post_reboot_probe"]["task_status"] == "COMPLETE"
    assert report["pre_reboot_probe"]["authorization_gate"] == "PASS"
    assert report["post_reboot_probe"]["authorization_gate"] == "PASS"
    assert dc.verify_device_campaign(campaign)


def test_changed_boot_hook_blocks_post_reboot_promotion(tmp_path, monkeypatch):
    campaign, hook, _ = _prepare(tmp_path, monkeypatch)
    hook.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
    monkeypatch.setattr(dc, "_read_boot_id", lambda: "boot-after")

    with pytest.raises(dc.DeviceCampaignError, match="hook changed"):
        dc.resume_device_campaign(campaign, boot_hook=hook)

    assert not (campaign / dc.REPORT_NAME).exists()


def test_final_manifest_detects_report_tampering(tmp_path, monkeypatch):
    campaign, hook, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(dc, "_read_boot_id", lambda: "boot-after")
    dc.resume_device_campaign(campaign, boot_hook=hook)
    assert dc.verify_device_campaign(campaign)

    report_path = campaign / dc.REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["checks"]["post_reboot_probe_verified"] = False
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")

    assert not dc.verify_device_campaign(campaign)
