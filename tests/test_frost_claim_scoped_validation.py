import os
import subprocess
from pathlib import Path

SCRIPT = Path("tools/dfir/FROST_ANDROID_EVIDENCE_GUARDIAN_v3.1.sh")
POLICY = Path("docs/validation/FROST_SENTINEL_VALIDATION_POLICY_v2.md")


def _status(tmp_path: Path, extra_env=None) -> str:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "FROST_EVIDENCE_HOME": str(tmp_path / "evidence"),
        }
    )
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["bash", str(SCRIPT), "status"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def test_policy_rejects_project_wide_physical_gate():
    text = POLICY.read_text(encoding="utf-8")
    assert "does **not** impose a project-wide requirement" in text
    assert "required_validation = minimum environment necessary to support the specific claim" in text
    assert "Lack of a handset run must never downgrade unrelated host-verifiable work" in text


def test_host_runtime_is_software_only(tmp_path):
    out = _status(tmp_path)
    assert "runtime_class=HOST_OR_SESSION" in out
    assert "claim_scope=SOFTWARE_ONLY" in out
    assert "sealed_evidence=PASS" in out


def test_android_fixture_is_not_device_origin(tmp_path):
    out = _status(tmp_path, {"FROST_ANDROID_FIXTURE": "1"})
    assert "runtime_class=ANDROID_FIXTURE" in out
    assert "claim_scope=ANDROID_LOGIC_AND_SOFTWARE" in out
    assert "DEVICE_ORIGIN_AND_SOFTWARE" not in out


def test_script_records_claim_scope_in_collections():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"$(runtime_class)" >"$d/meta/runtime_class.txt"' in text
    assert '"$(claim_scope)" >"$d/meta/claim_scope.txt"' in text


def test_simulation_cannot_be_promoted_to_device_origin_by_fixture_flag():
    text = SCRIPT.read_text(encoding="utf-8")
    fixture_branch = """elif [[ "${FROST_ANDROID_FIXTURE:-0}" == "1" ]]; then
    printf 'ANDROID_FIXTURE'"""
    assert fixture_branch in text
    assert "ANDROID_FIXTURE) printf 'ANDROID_LOGIC_AND_SOFTWARE'" in text
    assert "ANDROID_TERMUX) printf 'DEVICE_ORIGIN_AND_SOFTWARE'" in text
