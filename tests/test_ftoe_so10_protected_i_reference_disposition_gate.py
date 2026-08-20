from scripts import ftoe_so10_protected_i_reference_disposition_gate as gate


def test_failed_parent_kills_direct_identification() -> None:
    contract = {
        "parent_gate": "FAIL_DIRECT_IDENTIFICATION_HIGGS_ROLE_CONFLICT",
        "scientific_status": "FAIL",
        "disposition": "KILLED_FOR_DIRECT_IDENTIFICATION",
        "no_retuning": True,
        "publication_readiness": "REVIEW_FAIL_CLOSED",
        "scope_limit": "direct identification only",
    }
    result = gate.evaluate(contract)
    assert result["execution_pass"] is True
    assert result["scientific_verdict"] == "KILLED_FOR_DIRECT_IDENTIFICATION"
    assert result["scientific_pass"] is False


def test_disposition_fails_closed_if_parent_failure_missing() -> None:
    contract = {
        "parent_gate": "PASS",
        "scientific_status": "FAIL",
        "disposition": "KILLED_FOR_DIRECT_IDENTIFICATION",
        "no_retuning": True,
        "publication_readiness": "REVIEW_FAIL_CLOSED",
    }
    assert gate.evaluate(contract)["execution_pass"] is False
