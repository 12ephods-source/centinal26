from scripts.ftoe_so10_protected_i_so6_minimal_disposition_gate import evaluate


def valid_contract() -> dict:
    return {
        "scientific_status": "FAIL",
        "parent_gate": "FAIL_MINIMAL_REFERENCE_PORTAL_SUPPRESSION",
        "disposition": "KILLED_FOR_PROTECTED_I_ADMISSION",
        "no_retuning": True,
        "publication_readiness": "REVIEW_FAIL_CLOSED",
        "scope_limit": "This is not a no-go theorem against separately versioned successor classes.",
    }


def test_valid_disposition_executes_pass_but_science_remains_fail() -> None:
    result = evaluate(valid_contract())
    assert result["execution_pass"] is True
    assert result["scientific_pass"] is False
    assert result["scientific_verdict"] == "KILLED_FOR_PROTECTED_I_ADMISSION"


def test_cannot_kill_without_failed_parent_gate() -> None:
    contract = valid_contract()
    contract["parent_gate"] = "PASS"
    result = evaluate(contract)
    assert result["execution_pass"] is False
