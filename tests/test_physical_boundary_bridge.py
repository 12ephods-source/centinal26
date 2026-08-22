import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "termux" / "FROST_PHYSICAL_BOUNDARY_BRIDGE_v1.0.sh"


def test_bridge_syntax_and_invariants() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    text = SCRIPT.read_text(encoding="utf-8")
    for token in [
        "HOST_READY_DEVICE_EXECUTION_REQUIRED",
        "ADB_PAIRING_REQUIRED",
        "qualify_and_arm.sh",
        "disarm.sh",
        "FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh",
        "DEVICE_EVIDENCE_CAPTURED_PENDING_INDEPENDENT_VERIFICATION",
        "independent controller verification",
        "IMPROVEMENT_CYCLE_START",
        "CYCLE_CRITIQUE",
        "cleaner_disarmed_for_combined_cycle",
        "COMMISSION_FAILED",
        "CYCLE_HARD_BLOCKER",
        "no_retry_external_android_authorization",
    ]:
        assert token in text


def test_host_mode_is_non_physical_and_emits_handoff_receipt() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = os.environ.copy()
        env["HOME"] = td
        proc = subprocess.run(
            ["bash", str(SCRIPT), "host"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert "HOST_READY_DEVICE_EXECUTION_REQUIRED" in proc.stdout
        receipt = (
            Path(td)
            / ".local"
            / "share"
            / "frost-physical-boundary-bridge"
            / "host_handoff_receipt.json"
        )
        assert receipt.exists()
        content = receipt.read_text(encoding="utf-8")
        assert "HOST_READY_DEVICE_EXECUTION_REQUIRED" in content
        assert "independent controller verification" in content


def test_first_time_android_authorization_is_not_retried_as_transient() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "return 3" in text
    assert "no_retry_external_android_authorization" in text
    assert "retry_recoverable_only" in text


def test_cleaner_is_disarmed_before_combined_cycle() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    install = text.index("install_components(){")
    cycle = text.index("cycle(){")
    section = text[install:cycle]
    assert "library_cleaner/install.sh" in section
    assert "disarm.sh" in section
    assert section.index("library_cleaner/install.sh") < section.index("disarm.sh")


def test_commission_failure_preserves_evidence_and_disarms_cleaner() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("emit COMMISSION_START")
    section = text[start:]
    assert "COMMISSION_FAILED" in section
    assert "disarm.sh" in section
    assert "package_evidence || true" in section
