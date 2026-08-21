import re
from pathlib import Path

SCRIPT = Path("deploy/termux/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh")


def text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_fixed_physical_source_and_per_device_campaign():
    s = text()
    assert 'PERSIST_SHA="20dcbb6dae29eee302e2d566c2a4270d1b657971"' in s
    assert 'device-validation/devices/$device_id/current' in s
    assert 'device_campaign_cli identity' in s
    assert 'device_campaign_cli verify --campaign "$campaign"' in s


def test_registered_operations_are_bounded():
    s = text()
    for op in (
        "device.validation.status",
        "device.validation.ensure",
        "device.validation.verify",
    ):
        assert op in s
    assert "device.reboot" in s
    assert "deny-remote-reboot" in s
    assert "shell.exec" not in s
    assert "workflow.execute" not in s


def test_remote_job_cannot_choose_source_path_or_commit():
    s = text()
    assert 'PERSIST_SHA="20dcbb6dae29eee302e2d566c2a4270d1b657971"' in s
    assert 'REPO="https://github.com/12ephods-source/centinal26.git"' in s
    assert "requestedCapability(job)" not in s.split("cat > \"$ADAPTER\" <<'SH'", 1)[1].split("\nSH\n", 1)[0]
    assert re.search(r'case "\$MODE" in\s+status\|ensure\|verify\)', s)


def test_validation_adapter_never_reboots_android():
    s = text()
    helper = s.split("cat > \"$ADAPTER\" <<'SH'", 1)[1].split("\nSH\n", 1)[0]
    forbidden = ("reboot ", "svc power", "setprop sys.powerctl", "termux-reboot")
    assert all(token not in helper for token in forbidden)
    assert '"reboot_performed_by_adapter":False' in s


def test_worker_patch_is_fail_closed_to_expected_v11_contract():
    s = text()
    assert "worker source is not the expected v1.1 contract" in s
    assert 'const VERSION = "centinal26-base44-fleet-worker/1.1.0";' in s
    assert 'const VERSION = "centinal26-base44-fleet-worker/1.2.0";' in s
    assert 'node --check "$WORKER"' in s
    assert 'node "$WORKER" --self-test' in s
