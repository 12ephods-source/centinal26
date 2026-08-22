import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install/2026-08-22__FROST_RELEASE_STATUS_ONE_PASTE_v1.0.sh"


def test_release_status_script_executes_profile_on_python_312_plus():
    with tempfile.TemporaryDirectory() as tmp:
        state_root = pathlib.Path(tmp) / "state"
        state_root.mkdir()
        checks = {
            "repo_sync": True,
            "repo_clean": True,
            "pair_ok": True,
            "skynet_ok": True,
            "state_integrity_ok": True,
            "recovery_ok": True,
            "security_policy_ok": True,
            "device_boot_ok": False,
            "device_restart_ok": False,
            "device_exec_ok": False,
            "device_audit_ok": False,
        }
        (state_root / "project_state.json").write_text(
            json.dumps({"release": "test-release", "checks": checks}) + "\n"
        )
        env = os.environ.copy()
        env["CENTINAL26_ROOT"] = str(ROOT)
        env["FROST_PERSISTENT_STATE"] = str(state_root)
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["software_release_complete"] is True
        assert payload["deployed_app_complete"] is False
        assert payload["policy"]["finished_software_product_requires_device_evidence"] is False
        assert payload["policy"]["finished_deployed_app_requires_device_evidence"] is True
