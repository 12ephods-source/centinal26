from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "termux" / "FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"
COLLECTOR = ROOT / "automation" / "device" / "evidence_gate_collector.py"


def test_installer_uses_dedicated_repo_and_no_remote_reboot() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert ".local/share/frost-evidence-gate/repo" in text
    assert "pkg install -y git python coreutils curl age" in text
    assert "rclone" in text
    assert "reboot -p" not in text
    assert "adb reboot" not in text
    assert "su -c reboot" not in text
    assert "Perform a PHYSICAL reboot" in text


def test_collector_is_bound_to_qualified_commissioning_revision() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")
    assert 'QUALIFIED_DEVICE_SOURCE = "9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483"' in text
    assert '"promotion_performed": False' in text
    assert '"independent_judge_verified": False' in text
    assert '"lease_event_chain_verified": False' in text
