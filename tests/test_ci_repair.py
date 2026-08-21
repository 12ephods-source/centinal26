from centinal26.ci_repair import (
    FailureState,
    RepairKind,
    classify_failure,
    parse_ruff_diagnostics,
    receipt,
)


def test_superseded_failure_never_requests_mutation() -> None:
    plan = classify_failure(
        failing_sha="a" * 40,
        failing_log="anything",
        latest_sha="b" * 40,
        latest_equivalent_passed=True,
    )
    assert plan.state == FailureState.SUPERSEDED_FAILURE
    assert plan.kind == RepairKind.REVIEW_REQUIRED
    assert not plan.validation


def test_allowlisted_ruff_failure_gets_smallest_file_check() -> None:
    log = """UP035 [*] Import from collections.abc instead
  --> src/centinal26/chat_bridge.py:11:1
SIM117 Use a single with statement
  --> src/centinal26/chat_bridge.py:177:17
"""
    plan = classify_failure(failing_sha="a" * 40, failing_log=log)
    assert plan.state == FailureState.ACTIVE_FAILURE
    assert plan.kind == RepairKind.RUFF_SAFE
    assert [item.code for item in plan.diagnostics] == ["UP035", "SIM117"]
    assert plan.validation == ("ruff check src/centinal26/chat_bridge.py",)


def test_unknown_failure_fails_closed() -> None:
    plan = classify_failure(
        failing_sha="a" * 40,
        failing_log="AssertionError: production behavior changed",
    )
    assert plan.state == FailureState.REVIEW_REQUIRED
    assert plan.kind == RepairKind.REVIEW_REQUIRED


def test_non_allowlisted_ruff_diagnostic_fails_closed() -> None:
    log = """F821 Undefined name `missing`
  --> src/centinal26/example.py:9:3
"""
    plan = classify_failure(failing_sha="a" * 40, failing_log=log)
    assert plan.state == FailureState.REVIEW_REQUIRED
    assert plan.kind == RepairKind.REVIEW_REQUIRED
    assert [item.code for item in plan.diagnostics] == ["F821"]


def test_parser_preserves_multiple_files_without_cross_contamination() -> None:
    log = """I001 Import block is un-sorted or un-formatted
  --> tests/test_a.py:1:1
UP035 Import from collections.abc instead
  --> src/centinal26/b.py:8:1
"""
    diagnostics = parse_ruff_diagnostics(log)
    assert [(item.code, item.path, item.line) for item in diagnostics] == [
        ("I001", "tests/test_a.py", 1),
        ("UP035", "src/centinal26/b.py", 8),
    ]


def test_receipt_is_deterministic_and_bound_to_log_hash() -> None:
    plan = classify_failure(
        failing_sha="a" * 40,
        failing_log="I001 imports\n  --> tests/test_a.py:1:1\n",
    )
    first = receipt(plan, run_id=10, job_id=20, log_sha256="1" * 64)
    second = receipt(plan, run_id=10, job_id=20, log_sha256="1" * 64)
    changed = receipt(plan, run_id=10, job_id=20, log_sha256="2" * 64)
    assert first == second
    assert first["receipt_sha256"] != changed["receipt_sha256"]
