import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("epistemic_gate", ROOT / "scripts" / "epistemic_gate.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(mod)


def base_claim():
    return {
        "claim_id": "T",
        "statement": "test",
        "scope": "test",
        "claim_kind": "SOFTWARE_BEHAVIOR",
        "current_epistemic_status": "SUPPORTED",
        "dimensions": {
            "provenance_status": "PASS",
            "integrity_status": "PASS",
            "source_semantics_status": "PASS",
            "reproduction_status": "PASS",
            "independent_verification_status": "UNKNOWN",
            "device_validation_status": "NOT_APPLICABLE",
            "empirical_status": "NOT_APPLICABLE",
            "scientific_status": "NOT_APPLICABLE",
            "historical_verification_status": "NOT_APPLICABLE",
            "attribution_status": "NOT_APPLICABLE",
        },
        "support": [
            {"evidence_id": "e1", "class": "DIRECT_SOURCE", "independence_group": "g1", "integrity": "PASS"}
        ],
        "counterevidence": [],
        "unresolved_contradictions": [],
    }


def test_provenance_alone_does_not_establish():
    c = base_claim()
    c["support"] = [{"evidence_id": "e1", "class": "USER_REPORTED", "independence_group": "g1", "integrity": "PASS"}]
    c["current_epistemic_status"] = "ESTABLISHED_WITHIN_SCOPE"
    r = mod.evaluate_claim(c)
    assert r["gate_result"] == "FAIL"
    assert r["promotion_ceiling"] == "PLAUSIBLE"


def test_two_independent_lines_plus_independent_verification_can_strengthen():
    c = base_claim()
    c["support"].append({"evidence_id": "e2", "class": "REPRODUCED", "independence_group": "g2", "integrity": "PASS"})
    c["dimensions"]["independent_verification_status"] = "PASS"
    c["current_epistemic_status"] = "ESTABLISHED_WITHIN_SCOPE"
    r = mod.evaluate_claim(c)
    assert r["gate_result"] == "PASS"
    assert r["promotion_ceiling"] == "ESTABLISHED_WITHIN_SCOPE"


def test_blocked_device_gate_caps_claim():
    c = base_claim()
    c["claim_kind"] = "DEVICE_BEHAVIOR"
    c["dimensions"]["device_validation_status"] = "BLOCKED"
    c["dimensions"]["independent_verification_status"] = "PASS"
    c["support"].append({"evidence_id": "e2", "class": "INDEPENDENT_DIRECT", "independence_group": "g2", "integrity": "PASS"})
    c["current_epistemic_status"] = "SUPPORTED"
    r = mod.evaluate_claim(c)
    assert r["gate_result"] == "FAIL"
    assert r["promotion_ceiling"] == "PLAUSIBLE"


def test_contradiction_caps_at_supported():
    c = base_claim()
    c["support"].append({"evidence_id": "e2", "class": "INDEPENDENT_DIRECT", "independence_group": "g2", "integrity": "PASS"})
    c["dimensions"]["independent_verification_status"] = "PASS"
    c["unresolved_contradictions"] = ["material contradiction"]
    c["current_epistemic_status"] = "STRONGLY_SUPPORTED"
    r = mod.evaluate_claim(c)
    assert r["gate_result"] == "FAIL"
    assert r["promotion_ceiling"] == "SUPPORTED"


def test_rejection_requires_decisive_basis():
    c = base_claim()
    c["current_epistemic_status"] = "REJECTED"
    assert mod.evaluate_claim(c)["gate_result"] == "FAIL"
    c["counterevidence"] = [
        {"evidence_id": "x", "class": "DIRECT_SOURCE", "independence_group": "xg", "integrity": "PASS", "decisive_against_promotion": True}
    ]
    assert mod.evaluate_claim(c)["gate_result"] == "PASS"


def test_project_ledger_is_not_overpromoted():
    data = json.loads((ROOT / "automation" / "EPISTEMIC_CLAIM_LEDGER_v1.json").read_text())
    report = mod.evaluate_ledger(data)
    assert report["overall"] == "PASS"
    assert report["truth_determination"] == "NOT_PERFORMED"
