from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "termux" / "CENTINAL26_FROST_ONE_PASTE_v1.0.sh"
PINNED_COMMIT = "06e05e9c85c4449443e0424640cd6198cd1493a9"
OPENING = "Yes, I would be happy to help you with that request."


def _text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_installer_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(INSTALLER)], check=True)


def test_installer_pins_verified_canonical_commit() -> None:
    text = _text()
    assert f'PINNED_COMMIT="{PINNED_COMMIT}"' in text
    assert "https://github.com/12ephods-source/centinal26.git" in text
    assert "rev-parse HEAD" in text
    assert "status --porcelain --untracked-files=all" in text
    assert "main" not in text.split('PINNED_COMMIT="', 1)[1].split("\n", 1)[0]


def test_installer_uses_no_insecure_package_or_pipe_to_shell_bypass() -> None:
    text = _text()
    forbidden = (
        "--allow-unauthenticated",
        "allow-insecure-repositories",
        "trusted=yes",
        "curl | sh",
        "curl|sh",
        "wget | sh",
        "wget|sh",
    )
    for token in forbidden:
        assert token not in text


def test_installer_preserves_existing_files_instead_of_destructive_cleanup() -> None:
    text = _text()
    assert "rm -rf" not in text
    assert "recovery-$(date" in text


def test_safe_autopilot_wrapper_never_adds_broad_authorization() -> None:
    text = _text()
    start = text.index('cat > "$BIN_DIR/frost-safe-autopilot"')
    end = text.index('chmod 700 "$BIN_DIR/frost-safe-autopilot"', start)
    wrapper = text[start:end]
    assert "autopilot" in wrapper
    assert "--authorize" not in wrapper


def test_installer_persists_response_opening_policy() -> None:
    text = _text()
    assert f"RESPONSE_OPENING='{OPENING}'" in text
    assert "RESPONSE_OPENING_POLICY.txt" in text


def test_device_smoke_exercises_safe_execution_and_authorization_boundary() -> None:
    text = _text()
    assert "device-safe-smoke" in text
    assert "device-auth-smoke" in text
    assert "capability\": \"system.echo" in text
    assert '"authority": "authorization_required"' in text
    assert '[[ "$auth_rc" -eq 3 ]]' in text
    assert 'event.type == "TASK_STARTED"' in text
    assert 'event.payload.get("reason") == "APPROVAL_REQUIRED"' in text


def test_boot_autopilot_is_opt_in_and_safe_only() -> None:
    text = _text()
    assert 'CENTINAL26_ENABLE_BOOT_AUTOPILOT:-0' in text
    assert "frost-safe-autopilot" in text
    assert "autonomous_external_side_effects" in text


def test_installer_records_precise_validation_scope() -> None:
    text = _text()
    assert '"status": "DEVICE_INSTALL_SMOKE_PASS"' in text
    for unclaimed in (
        "reboot_persistence",
        "long-duration_endurance",
        "remote_phone_worker_end_to_end",
        "autonomous_external_side_effects",
    ):
        assert unclaimed in text
