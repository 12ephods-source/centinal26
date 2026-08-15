from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_finalizer_separates_historical_rc4_from_current_ga():
    finalizer = text("termux/automation_project_finalizer.sh")
    state = text("releases/CURRENT_RELEASE_STATE.json")
    assert "recover-rc4-parent-inputs.sh" in finalizer
    assert "current_ga_blocker:false" in finalizer
    assert '"blocks_current_ga": false' in state
    assert "HISTORICAL_PROVENANCE_RECOVERY" in state


def test_current_worker_is_single_command_allowlisted_and_fail_closed():
    worker = text("termux/intelligence_controller_github_worker_once.sh")
    assert 'ALLOWED_COMMAND="automation_project_finalize_v1"' in worker
    assert "DENIED_UNSUPPORTED_COMMAND" in worker
    assert "exit 65" in worker
    assert "automation.github_job/v2" in worker
    assert "intelligence_controller_physical_gate_v1" not in worker


def test_endurance_gate_uses_conservative_physical_thresholds():
    endurance = text("termux/intelligence_node_endurance.sh")
    assert 'SAMPLES="${CENTINAL26_ENDURANCE_SAMPLES:-61}"' in endurance
    assert 'INTERVAL="${CENTINAL26_ENDURANCE_INTERVAL:-60}"' in endurance
    assert 'MIN_SECONDS="${CENTINAL26_ENDURANCE_MIN_SECONDS:-3500}"' in endurance
    assert "DENIED_UNSUPPORTED_COMMAND" in endurance
    assert "recovery_pass" in endurance
    assert "event_chain_valid" in endurance


def test_independent_verifier_recomputes_raw_evidence():
    verifier = text("termux/verify_project_finalization.py")
    assert "independent-python-evidence-verifier/v1" in verifier
    assert 'load("post_reboot.json")' in verifier
    assert 'load("endurance_report.json")' in verifier
    assert "endurance_samples.jsonl" in verifier
    assert "sample_hash_matches" in verifier
    assert "device_sync_endurance_binding" in verifier


def test_no_remote_reboot_or_arbitrary_shell_in_finalization_surface():
    combined = "\n".join(
        text(path)
        for path in (
            "termux/automation_project_finalizer.sh",
            "termux/intelligence_node_endurance.sh",
            "termux/intelligence_controller_github_worker_once.sh",
            "termux/intelligence_controller_report_after_reboot.sh",
        )
    )
    for forbidden in ("sudo reboot", "termux-reboot", 'eval "$', 'bash -c "$command'):
        assert forbidden not in combined


def test_installer_includes_finalizer_endurance_and_verifier():
    installer = text("termux/install_intelligence_github_control.sh")
    assert "automation_project_finalizer.sh" in installer
    assert "intelligence_node_endurance.sh" in installer
    assert "verify_project_finalization.py" in installer
    assert "recover-rc4-parent-inputs.sh" in installer
