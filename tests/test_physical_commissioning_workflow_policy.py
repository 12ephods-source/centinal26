from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "request-physical-ga.yml"


def test_manual_physical_workflow_is_guidance_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Prepare Android Physical Commissioning" in text
    assert "automation/PROJECT_STATE.json" in text
    assert ".physical_gate.qualified_source_commit" in text
    assert ".physical_gate.tracker_issue" in text
    assert "ONE_ANDROID_RUN_PLUS_CONTROLLER_VERIFICATION" in text
    assert "This workflow does not enqueue or claim a device job." in text


def test_manual_physical_workflow_cannot_enqueue_legacy_rc9_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "automation_os_physical_ga_rc9_integrity" not in text
    assert "issues: write" not in text
    assert '"https://api.github.com/repos/${GH_REPO}/issues"' not in text
    assert "automation-os-job" not in text
