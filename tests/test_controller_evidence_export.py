from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "automation" / "controller" / "base44_evidence_export.mjs"
INSTALLER = ROOT / "deploy" / "termux" / "FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"
ENTITY_WRITE_RE = re.compile(
    r"base44(?:\.asServiceRole)?\.entities\.[A-Za-z0-9_]+\."
    r"(?:create|update|delete|bulkCreate|deleteMany)\("
)


def test_controller_exporter_is_read_only_and_user_rls_scoped() -> None:
    text = EXPORTER.read_text(encoding="utf-8")
    assert 'access_mode: "AUTHENTICATED_USER_RLS"' in text
    assert ENTITY_WRITE_RE.search(text) is None
    assert "asServiceRole" not in text
    assert "loginViaEmailPassword" in text
    assert "--password-stdin" in text
    assert "password arguments are forbidden" in text


def test_controller_exporter_collects_required_physical_gate_entities() -> None:
    text = EXPORTER.read_text(encoding="utf-8")
    for entity in (
        "AutomationWorker",
        "AutomationJob",
        "AutomationLease",
        "AutomationAudit",
        "AutomationResult",
        "AutomationRebootEvidence",
        "AutomationBootSentinel",
        "AutomationPhysicalGate",
        "AutomationWorkContract",
        "AutomationRoleResult",
        "AutomationVerificationVerdict",
        "AutomationFleetMetric",
    ):
        assert entity in text
    assert "device_validated_controller_evidence_eligible" in text
    assert "persistent_validated_controller_evidence_eligible" in text
    assert "promotion_performed: false" in text


def test_installer_keeps_password_out_of_arguments_and_preserves_physical_reboot() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "pkg install -y git python coreutils curl age nodejs" in text
    assert "@base44/sdk" in text
    assert "read -r -s -p 'Base44 password: '" in text
    assert "--password-stdin" in text
    assert "--password " not in text
    assert "Perform a PHYSICAL reboot" in text
    assert "adb reboot" not in text
    assert "su -c reboot" not in text
