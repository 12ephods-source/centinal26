from centinal26.ci_repair import FailureState, RepairKind, classify_failure


def test_superseded_failure_never_requests_mutation():
    plan = classify_failure(
        failing_sha="a" * 40,
        failing_log="anything",
        latest_sha="b" * 40,
        latest_equivalent_passed=True,
    )
    assert plan.state == FailureState.SUPERSEDED_FAILURE
    assert plan.kind == RepairKind.REVIEW_REQUIRED
    assert not plan.validation


def test_allowlisted_ruff_failure_gets_smallest_file_check():
    log = """UP035 [*] Import from collections.abc instead\n  --> src/centinal26/chat_bridge.py:11:1\nSIM117 Use a single with statement\n  --> src/centinal26/chat_bridge.py:177:17\n"""
    plan = classify_failure(failing_sha="a" * 40, failing_log=log)
    assert plan.state == FailureState.ACTIVE_FAILURE
    assert plan.kind == RepairKind.RUFF_SAFE
    assert [item.code for item in plan.diagnostics] == ["UP035", "SIM117"]
    assert plan.validation == ("ruff check src/centinal26/chat_bridge.py",)


def test_unknown_failure_fails_closed():
    plan = classify_failure(
        failing_sha="a" * 40,
        failing_log="AssertionError: production behavior changed",
    )
    assert plan.state == FailureState.REVIEW_REQUIRED
    assert plan.kind == RepairKind.REVIEW_REQUIRED
