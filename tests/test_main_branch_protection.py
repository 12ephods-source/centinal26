from __future__ import annotations

import json
from pathlib import Path

from scripts.reconcile_main_branch_protection import (
    audit_observed,
    protection_payload,
    validate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "automation/governance/main_branch_protection.json"


def _policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _observed(policy: dict) -> dict:
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": list(policy["required_status_checks"]["contexts"]),
        },
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "required_approving_review_count": 0,
        },
        "enforce_admins": {"enabled": True},
        "required_conversation_resolution": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }


def test_policy_is_fail_closed_and_tracks_issue_271() -> None:
    policy = _policy()
    validate_policy(policy)
    assert policy["tracker_issue"] == 271
    assert policy["autonomous_reconciliation"]["server_readback_required"] is True
    assert policy["autonomous_reconciliation"]["workflow_substitution_allowed"] is False
    assert policy["emergency_override"]["ordinary_admin_bypass"] is False


def test_payload_requires_pr_checks_and_blocks_force_delete() -> None:
    policy = _policy()
    payload = protection_payload(policy)
    assert payload["enforce_admins"] is True
    assert payload["required_pull_request_reviews"] is not None
    assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 0
    assert payload["required_status_checks"]["strict"] is True
    assert "governance-policy" in payload["required_status_checks"]["contexts"]
    assert payload["allow_force_pushes"] is False
    assert payload["allow_deletions"] is False


def test_unprotected_branch_is_drift() -> None:
    result = audit_observed(_policy(), None)
    assert result.status == "DRIFT"
    assert result.drift == ("branch_unprotected",)


def test_matching_server_readback_converges() -> None:
    policy = _policy()
    result = audit_observed(policy, _observed(policy))
    assert result.converged is True
    assert result.drift == ()


def test_missing_check_and_force_push_are_detected() -> None:
    policy = _policy()
    observed = _observed(policy)
    observed["required_status_checks"]["contexts"].remove("release-engineering")
    observed["allow_force_pushes"] = {"enabled": True}
    result = audit_observed(policy, observed)
    assert result.status == "DRIFT"
    assert any(item.startswith("missing_required_status_checks:") for item in result.drift)
    assert "force_push_policy_mismatch" in result.drift


def test_dynamic_convergence_is_bound_to_always_required_context() -> None:
    policy = _policy()
    dynamic = policy["dynamic_release_convergence"]
    assert dynamic["enforced_by_context"] == "governance-policy"
    assert "releases/RELEASE_CONTRACT.json" in dynamic["paths"]
    assert "scripts/validate_release_convergence.py" in dynamic["paths"]
