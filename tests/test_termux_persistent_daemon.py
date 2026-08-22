from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "termux" / "centinal26_daemon.py"
CTL = ROOT / "termux" / "centinal26ctl.py"
INSTALLER = ROOT / "termux" / "CENTINAL26_TERMUX_ONE_PASTE_INSTALLER_v1.sh"
MANIFEST = ROOT / "automation" / "TERMUX_EXECUTION_PLANE.json"


def test_python_sources_parse():
    ast.parse(DAEMON.read_text())
    ast.parse(CTL.read_text())


def test_manifest_preserves_physical_truth_boundary():
    m = json.loads(MANIFEST.read_text())
    assert m["controller_relationship"] == "capability_of_existing_autopilot_not_competing_controller"
    rules = m["promotion_rules"]
    assert rules["github_ci_is_not_device_execution"] is True
    assert rules["host_or_simulation_is_not_device_execution"] is True
    assert rules["llm_statement_is_not_device_execution"] is True
    assert rules["device_tested_requires_authentic_device_origin_and_independent_verification"] is True


def test_daemon_uses_transactional_single_claim_and_idempotency():
    text = DAEMON.read_text()
    assert "BEGIN IMMEDIATE" in text
    assert "idempotency_key TEXT NOT NULL UNIQUE" in text
    assert "lease_until" in text
    assert "RETRY_WAIT" in text
    assert "random.randint" in text


def test_no_arbitrary_shell_execution_path():
    tree = ast.parse(DAEMON.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"run", "Popen"}:
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
                    assert kw.value.value is not True
    assert "eval(" not in DAEMON.read_text()
    assert "exec(" not in DAEMON.read_text()


def test_installer_is_fail_closed_and_boot_integrated():
    text = INSTALLER.read_text()
    assert "set -euo pipefail" in text
    assert "python -m py_compile" in text
    assert "bash -n" in text
    assert "start-centinal26.sh" in text
    assert "centinal26-uninstall.sh" in text
    assert "does not claim device-tested status" in text


def test_provider_layer_is_explicit_and_secret_averse():
    text = DAEMON.read_text()
    assert "providers.json" in text
    assert "provider/capability not configured" in text
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["adapter_policy"]["provider_neutral"] is True
    assert manifest["adapter_policy"]["secret_serialization_forbidden"] is True
