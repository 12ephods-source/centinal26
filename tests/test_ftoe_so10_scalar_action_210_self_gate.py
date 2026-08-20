from scripts import ftoe_so10_scalar_action_210_self_gate as gate


def test_sourced_210_self_sector_passes_execution_but_not_full_action() -> None:
    contract = {
        "renormalizable_self_sector": {
            "quadratic_invariant_count": 1,
            "cubic_invariant_count": 1,
            "quartic_invariant_count": 4,
        },
        "primary_sources": [{"arxiv": "hep-ph/0306242"}, {"arxiv": "gr-qc/9512033"}],
        "full_action_gate": "NOT_COMPLETE",
        "still_unenumerated": ["a", "b", "c", "d"],
        "no_retuning": True,
        "publication_readiness": "REVIEW_FAIL_CLOSED",
    }
    result = gate.evaluate(contract)
    assert result["execution_pass"] is True
    assert result["scientific_verdict"] == "PARTIAL_ACTION_210_SELF_SECTOR_SOURCE_ENUMERATED"
    assert result["scientific_pass"] is False
    assert result["full_action_complete"] is False


def test_gate_fails_if_full_action_is_claimed_complete() -> None:
    contract = {
        "renormalizable_self_sector": {
            "quadratic_invariant_count": 1,
            "cubic_invariant_count": 1,
            "quartic_invariant_count": 4,
        },
        "primary_sources": [{}, {}],
        "full_action_gate": "COMPLETE",
        "still_unenumerated": ["a", "b", "c", "d"],
        "no_retuning": True,
        "publication_readiness": "REVIEW_FAIL_CLOSED",
    }
    assert gate.evaluate(contract)["execution_pass"] is False
