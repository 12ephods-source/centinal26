from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "termux" / "library_cleaner" / "install.sh"


def installer_text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_installer_disarms_before_first_device_qualification() -> None:
    text = installer_text()
    assert 'config["auto_delete"] = False' in text
    assert 'sv down "$SERVICE"' in text
    assert '"$APP/qualify_and_arm.sh"' in text


def test_installer_arms_only_after_zero_error_dry_run() -> None:
    text = installer_text()
    dry_run = text.index('frost_library_cleanerd.py" dry-run')
    zero_error_check = text.index('not result.get("errors")')
    arm = text.index('config["auto_delete"] = True')
    start = text.index('sv up "$SERVICE"', arm)
    assert dry_run < zero_error_check < arm < start


def test_boot_hook_starts_only_when_configuration_is_armed() -> None:
    text = installer_text()
    assert 'get("auto_delete") is True' in text
    assert 'sv up "$PREFIX/var/service/frost-library-cleaner"' in text
    assert 'sv down "$PREFIX/var/service/frost-library-cleaner"' in text


def test_disarm_control_stops_service_and_clears_arm() -> None:
    text = installer_text()
    assert 'cat > "$APP/disarm.sh"' in text
    disarm = text.index('cat > "$APP/disarm.sh"')
    segment = text[disarm:]
    assert 'sv down "$SERVICE"' in segment
    assert 'config["auto_delete"] = False' in segment
