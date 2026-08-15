from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parents[1]
BRIDGE = ROOT / "deploy" / "hermes-c05" / "hermes_c05_bridge.py"
PLUGIN = ROOT / "deploy" / "hermes-c05" / "plugin" / "frost_orchestrator"
TOOLS = PLUGIN / "tools.py"
INSTALLER = ROOT / "deploy" / "termux" / "HERMES_C05_FROST_FULL_ONE_PASTE_v1.0.sh"


def bridge_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HERMES_C05_HOME"] = str(tmp_path / "hermes-c05")
    env["CENTINAL26_HOME"] = str(tmp_path / "centinal26")
    return env


def run_bridge(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BRIDGE), *args],
        env=bridge_env(tmp_path),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_bridge_selftest_and_audit_chain(tmp_path: Path) -> None:
    result = run_bridge(tmp_path, "selftest")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["immutable_staging"] is True
    assert payload["idempotent_staging"] is True
    assert payload["audit_chain"] is True
    assert payload["no_external_publish"] is True

    audit = run_bridge(tmp_path, "verify-audit")
    assert audit.returncode == 0, audit.stderr
    assert json.loads(audit.stdout)["audit_valid"] is True


def test_local_a0_call_runs_through_real_centinal26_and_verifies(tmp_path: Path) -> None:
    result = run_bridge(
        tmp_path,
        "call",
        "system.echo",
        "--request-id",
        "hermes-c05-test-echo",
        "--json",
        '{"message":"adapter-test"}',
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "frost-call/1.0"
    assert payload["provider"] == "local-c05"
    assert payload["capability"] == "system.echo"
    assert payload["state"] == "verified"
    assert payload["verified"] is True
    assert payload["audit_valid"] is True
    assert payload["result"]["output"]["echo"]["message"] == "adapter-test"


def test_connected_request_is_translated_but_not_published(tmp_path: Path) -> None:
    result = run_bridge(
        tmp_path,
        "call",
        "frost.diagnostics.sha256",
        "--provider",
        "github",
        "--request-id",
        "hermes-c05-test-github",
        "--json",
        '{"text":"abc"}',
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "STAGED_LOCAL_ONLY"
    assert payload["provider"] == "github-actions"

    request_path = tmp_path / "hermes-c05" / "requests" / "hermes-c05-test-github.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["protocol"] == "frost-call/1.0"
    assert request["kind"] == "invoke"
    assert request["service_id"] == "frost.callable.fabric"
    assert request["operation"] == "frost.diagnostics.sha256"
    assert request["arguments"] == {"text": "abc"}
    assert request["context"]["approved"] is False
    assert request["context"]["source"] == "hermes"


def test_model_callable_plugin_has_no_direct_user_approval_channel() -> None:
    text = TOOLS.read_text(encoding="utf-8")
    start = text.index("def c05_call")
    end = text.index("def stage_script_inert")
    model_handler = text[start:end]
    assert "--user-approve" not in model_handler
    assert "approval_token" not in model_handler
    assert "shell=True" not in text


def test_script_compatibility_path_is_inert() -> None:
    text = TOOLS.read_text(encoding="utf-8")
    start = text.index("def stage_script_inert")
    end = text.index("def status_command")
    stage_handler = text[start:end]
    assert '"execution": False' in stage_handler
    assert '"authorization": False' in stage_handler
    assert '"status": "PRESERVED_INERT"' in stage_handler
    assert "subprocess" not in stage_handler


def test_plugin_registers_c05_tools_commands_and_skill() -> None:
    init_text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    for name in ("frost_c05_call", "frost_c05_status", "frost_stage_script"):
        assert f'name="{name}"' in init_text
    for name in (
        "frost-status",
        "frost-call",
        "frost-approve",
        "frost-relay",
        "frost-protocol",
    ):
        assert f'"{name}"' in init_text
    assert 'ctx.register_skill("frost-c05-execution", skill)' in init_text


def test_one_paste_installer_is_syntax_valid_and_pinned() -> None:
    result = subprocess.run(
        ["bash", "-n", str(INSTALLER)],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = INSTALLER.read_text(encoding="utf-8")
    assert "22cd324ea56731701670c65037857dfa8c51fc5f" in text
    assert "c23d8a1004df13eccfa2fec82835f2bce1274d2aed92a633df49734ca51aef8a" in text
    assert "322e16d78b8eeb0940e0083f69e9d3720b3b2f383715d9cc180e60ff40c44df9" in text
    assert "Direct /frost-approve script execution has been retired" in text
    assert "migration_archives/frost_orchestrator-pre-c05" in text
