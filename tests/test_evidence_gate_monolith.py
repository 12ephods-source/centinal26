from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONOLITH = ROOT / "deploy" / "termux" / "FROST_EVIDENCE_GATE_MONOLITH_ONE_PASTE_v1.2.sh"


def test_monolith_shell_syntax() -> None:
    subprocess.run(["bash", "-n", str(MONOLITH)], check=True)


def test_monolith_preserves_reboot_boundary_and_resume_order() -> None:
    text = MONOLITH.read_text(encoding="utf-8")
    resume = text.index('if [ -s "${PRE_REBOOT}" ]')
    commission = text.index('frost-evidence-gate commission')
    assert resume < commission
    assert "frost-evidence-gate post-reboot" in text
    assert "post-reboot capture" in text
    assert "Physically reboot the Android phone" in text
    assert "adb reboot" in text  # explicitly named only as a forbidden action
    assert "Do NOT use adb reboot" in text
    assert "su -c reboot" in text  # explicitly named only as a forbidden action
    assert "remote shell reboot" in text


def test_monolith_runs_all_evidence_surfaces_without_promotion() -> None:
    text = MONOLITH.read_text(encoding="utf-8")
    for required in (
        "frost-evidence-gate doctor",
        "frost-controller-evidence self-test",
        "frost-evidence-gate init-age",
        "frost-evidence-gate commission",
        "offdevice-roundtrip",
        "worker-once",
        "frost-controller-evidence",
        "arm-reboot",
        "frost-evidence-gate status",
        '"promotion_performed":False',
    ):
        assert required in text


def test_monolith_does_not_embed_secrets_or_remote_mutation() -> None:
    text = MONOLITH.read_text(encoding="utf-8")
    assert "BASE44_EVIDENCE_PASSWORD=" not in text
    assert "rclone delete" not in text
    assert "rclone purge" not in text
    assert "asServiceRole" not in text
    assert "AutomationPromotion" not in text
