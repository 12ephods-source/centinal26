import json
import sys
from pathlib import Path

import pytest

from centinal26 import device_campaign_cli as cli
from centinal26.device_campaign import DeviceCampaignError


def _isolate_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CENTINAL26_HOME", str(tmp_path / "state"))
    (tmp_path / "home").mkdir(parents=True)


def test_device_id_persists_across_process_environment(tmp_path, monkeypatch):
    _isolate_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AUTOMATION_DEVICE_ID", "android-phone-a")

    first = cli._load_or_create_device_id()
    monkeypatch.delenv("AUTOMATION_DEVICE_ID")
    second = cli._load_or_create_device_id()

    assert first == "android-phone-a"
    assert second == first
    identity_path = Path(tmp_path / "state" / "device-identity.json")
    assert identity_path.is_file()


def test_persisted_device_id_rejects_conflicting_environment(tmp_path, monkeypatch):
    _isolate_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AUTOMATION_DEVICE_ID", "android-phone-a")
    assert cli._load_or_create_device_id() == "android-phone-a"

    monkeypatch.setenv("AUTOMATION_DEVICE_ID", "android-phone-b")
    with pytest.raises(DeviceCampaignError, match="conflicts with persisted"):
        cli._load_or_create_device_id()


def test_campaign_binding_rejects_other_phone_identity(tmp_path, monkeypatch):
    _isolate_home(tmp_path, monkeypatch)
    campaign = tmp_path / "campaign"
    campaign.mkdir()

    cli._write_device_binding(campaign, "android-phone-a")
    cli._verify_device_binding(campaign, "android-phone-a")

    with pytest.raises(DeviceCampaignError, match="different physical Termux identity"):
        cli._verify_device_binding(campaign, "android-phone-b")


def test_identity_command_exposes_local_executor_without_pinning_work(
    tmp_path, monkeypatch, capsys
):
    _isolate_home(tmp_path, monkeypatch)
    monkeypatch.setenv("AUTOMATION_DEVICE_ID", "android-phone-b")
    monkeypatch.setattr(sys, "argv", ["device_campaign_cli", "identity"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"device_id": "android-phone-b"}
