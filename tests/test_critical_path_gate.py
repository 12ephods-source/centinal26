import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "critical_path_gate.py"
POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "critical_path_policy.json"
SPEC = importlib.util.spec_from_file_location("critical_path_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_missing_class_is_deferred_while_blockers_are_active():
    verdict = GATE.classify(POLICY, "")
    assert verdict["decision"] == "DEFER"
    assert verdict["reason"] == "missing_critical_path_class"


def test_physical_validation_is_allowed_for_issue_64():
    body = """Critical-Path-Class: physical-validation
Critical-Path-Blocker: physical-ga:#64
Critical-Path-Result: sealed authentic Android campaign receipt
"""
    verdict = GATE.classify(POLICY, body)
    assert verdict["decision"] == "ALLOW"
    assert verdict["blocker"] == "physical-ga:#64"


def test_provider_records_are_allowed_for_external_evidence():
    body = """Critical-Path-Class: provider-records
Critical-Path-Blocker: external-evidence
Critical-Path-Result: authenticated provider session ledger
"""
    verdict = GATE.classify(POLICY, body)
    assert verdict["decision"] == "ALLOW"


def test_architecture_expansion_is_deferred_even_with_a_blocker_name():
    body = """Critical-Path-Class: architecture-expansion
Critical-Path-Blocker: physical-ga:#64
Critical-Path-Result: broader architecture
"""
    verdict = GATE.classify(POLICY, body)
    assert verdict["decision"] == "DEFER"
    assert verdict["reason"] == "work_class_not_allowed"


def test_wrong_blocker_for_allowed_class_is_deferred():
    body = """Critical-Path-Class: provider-records
Critical-Path-Blocker: physical-ga:#64
Critical-Path-Result: provider records
"""
    verdict = GATE.classify(POLICY, body)
    assert verdict["decision"] == "DEFER"
    assert verdict["reason"] == "class_not_allowed_for_blocker"


def test_explicit_deferred_state_is_fail_closed():
    verdict = GATE.classify(POLICY, "Critical-Path-State: DEFERRED")
    assert verdict["decision"] == "DEFER"
    assert verdict["reason"] == "explicitly_deferred"


def test_closing_physical_gate_does_not_release_external_evidence_gate():
    body = """Critical-Path-Class: provider-records
Critical-Path-Blocker: external-evidence
Critical-Path-Result: authenticated export
"""
    verdict = GATE.classify(
        POLICY,
        body,
        overrides={"physical-ga:#64": "CLOSED"},
    )
    assert verdict["decision"] == "ALLOW"
    assert "physical-ga:#64" not in verdict["active_blockers"]
    assert verdict["active_blockers"]["external-evidence"] == "WAITING_EXTERNAL"


def test_gate_becomes_inactive_only_when_all_blockers_are_terminal():
    verdict = GATE.classify(
        POLICY,
        "",
        overrides={
            "physical-ga:#64": "CLOSED",
            "external-evidence": "IRRECOVERABLE",
        },
    )
    assert verdict["decision"] == "ALLOW"
    assert verdict["reason"] == "critical_path_inactive"
    assert verdict["active_blockers"] == {}
