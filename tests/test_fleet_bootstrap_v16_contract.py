from pathlib import Path

SCRIPT = Path("deploy/termux/FROST_FLEET_BOOTSTRAP_v1.6.sh")


def text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_v16_pins_qualified_base_and_merged_adapter():
    s = text()
    assert 'BASE_COMMIT="0013c697c4d500d8aff62564a562b167f6458c7a"' in s
    assert 'BASE_BLOB="da696b4fbe58f6ece86a11a98a2bd6976daeea50"' in s
    assert 'ADAPTER_COMMIT="fa9e2a8c7185e84bc1ca0be90256eefc458656e2"' in s
    assert 'ADAPTER_BLOB="0b5d7b00ce4d8dd0af0ca7a73dcc40124c1dc647"' in s


def test_v16_verifies_before_both_executions():
    s = text()
    assert s.index('fetch_verified "$BASE_COMMIT"') < s.index('bash "$BASE"')
    assert s.index('fetch_verified "$ADAPTER_COMMIT"') < s.index('bash "$ADAPTER"')
    assert "sha1sum" in s
    assert "Git blob identity mismatch" in s
    assert 'bash -n "$out"' in s


def test_v16_preserves_bounded_remote_surface():
    s = text()
    for op in (
        "system.health",
        "system.capabilities",
        "capability.ensure",
        "device.validation.status",
        "device.validation.ensure",
        "device.validation.verify",
    ):
        assert op in s
    assert "remote Android reboot: disabled" in s
    assert "arbitrary remote shell: disabled" in s
    assert "arbitrary remote source/path/package selection: disabled" in s


def test_v16_does_not_add_remote_reboot_or_shell_executor():
    s = text()
    assert "device.reboot" not in s
    assert "shell.exec" not in s
    assert "workflow.execute" not in s
    assert "eval " not in s


def test_v16_delegates_instead_of_copying_device_campaign_logic():
    s = text()
    assert 'BASE_PATH="deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh"' in s
    assert 'ADAPTER_PATH="deploy/termux/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"' in s
    assert "device_campaign_cli" not in s
    assert "device-validation-termux.sh" not in s
