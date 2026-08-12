from __future__ import annotations

from centinal26.evolution import CandidateEvidence, GoalSpec, select_candidate


def goal() -> GoalSpec:
    return GoalSpec.from_dict(
        {
            "schema": "centinal26-goal-v1",
            "goal_id": "demo-goal",
            "objective": "Improve a bounded source module without weakening evaluators.",
            "include_paths": ["src/centinal26"],
            "goal_tests": ["tests/test_core.py"],
            "allowed_change_prefixes": ["src/centinal26/"],
            "max_cycles": 3,
            "candidates_per_cycle": 2,
        }
    )


def candidate(
    candidate_id: str,
    score: float,
    *,
    passed: bool = True,
    commit: str | None = "abc123",
    reasons: tuple[str, ...] = (),
) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=candidate_id,
        agent="goose-chat-patch-only",
        base_commit="base123",
        patch_sha256="1" * 64,
        changed_paths=("src/centinal26/example.py",),
        security_decision="ALLOW_STATIC_ONLY",
        validation_passed=passed,
        validation_results=(),
        score=score,
        commit=commit,
        rejection_reasons=reasons,
    )


def test_goal_tests_are_immutable_by_default() -> None:
    spec = goal()
    allowed, reason = spec.permits_changed_path("tests/test_core.py")
    assert allowed is False
    assert reason.startswith("protected:")


def test_security_and_termux_control_are_immutable_by_default() -> None:
    spec = goal()
    for path in (
        "SECURITY.md",
        "security/reviewed_artifacts.json",
        "pyproject.toml",
        "scripts/audit_untrusted_candidate.py",
        "scripts/controlled_evolution_loop.py",
        "scripts/run-controlled-evolution.sh",
        "termux/github_termux_worker_once.sh",
        "src/centinal26/core.py",
        "src/centinal26/evolution.py",
    ):
        allowed, _ = spec.permits_changed_path(path)
        assert allowed is False


def test_allowed_source_path_is_permitted() -> None:
    allowed, reason = goal().permits_changed_path("src/centinal26/example.py")
    assert allowed is True
    assert reason == "allowed"


def test_candidate_requires_measured_improvement() -> None:
    selected = select_candidate(
        [candidate("same", 0.70), candidate("better", 0.80)],
        baseline_score=0.70,
    )
    assert selected is not None
    assert selected.candidate_id == "better"


def test_invalid_or_uncommitted_candidate_cannot_promote() -> None:
    selected = select_candidate(
        [
            candidate("failed", 1.0, passed=False),
            candidate("rejected", 1.0, reasons=("security:DENY",)),
            candidate("uncommitted", 1.0, commit=None),
        ],
        baseline_score=0.20,
    )
    assert selected is None


def test_goal_test_must_live_under_tests() -> None:
    value = {
        "schema": "centinal26-goal-v1",
        "goal_id": "bad-goal",
        "objective": "Do not accept mutable self-authored evaluators.",
        "include_paths": ["src"],
        "goal_tests": ["src/fake_test.py"],
        "allowed_change_prefixes": ["src/"],
    }
    try:
        GoalSpec.from_dict(value)
    except ValueError as exc:
        assert "goal_tests must live under tests/" in str(exc)
    else:
        raise AssertionError("goal spec accepted an unprotected evaluator")
