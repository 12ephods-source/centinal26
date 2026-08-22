from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"


@dataclass(frozen=True)
class AuditResult:
    status: str
    drift: tuple[str, ...]
    observed: dict[str, Any]

    @property
    def converged(self) -> bool:
        return self.status == "CONVERGED" and not self.drift


def _load_policy(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("branch-protection policy must be a JSON object")
    validate_policy(value)
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    assert policy["schema"] == "automation.main_branch_protection_policy/v1"
    assert policy["repository"] == "12ephods-source/centinal26"
    assert policy["branch"] == "main"
    assert policy["tracker_issue"] == 271
    assert policy["required_pull_request"] is True
    assert policy["required_approving_review_count"] == 0
    assert policy["dismiss_stale_reviews"] is True
    assert policy["require_conversation_resolution"] is True
    assert policy["enforce_admins"] is True
    assert policy["allow_force_pushes"] is False
    assert policy["allow_deletions"] is False
    checks = policy["required_status_checks"]
    assert checks["strict"] is True
    contexts = checks["contexts"]
    assert contexts == list(dict.fromkeys(contexts))
    required = {
        "baseline",
        "callable-adapter",
        "test (3.11)",
        "test (3.12)",
        "test (3.13)",
        "vertical-slice",
        "host-federation-gate",
        "host-qualification",
        "release-engineering",
        "governance-policy",
    }
    assert required.issubset(set(contexts))
    dynamic = policy["dynamic_release_convergence"]
    assert dynamic["validator"] == "scripts/validate_release_convergence.py"
    assert dynamic["enforced_by_context"] == "governance-policy"
    assert dynamic["paths"]
    autonomous = policy["autonomous_reconciliation"]
    assert autonomous["controller"] == "scripts/reconcile_main_branch_protection.py"
    assert autonomous["workflow"] == ".github/workflows/governance-enforcement.yml"
    assert autonomous["server_readback_required"] is True
    assert autonomous["workflow_substitution_allowed"] is False
    assert policy["emergency_override"]["ordinary_admin_bypass"] is False
    assert policy["evidence_boundary"]["branch_protection_is_physical_device_evidence"] is False


def protection_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "required_status_checks": {
            "strict": policy["required_status_checks"]["strict"],
            "contexts": policy["required_status_checks"]["contexts"],
        },
        "enforce_admins": policy["enforce_admins"],
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": policy["dismiss_stale_reviews"],
            "require_code_owner_reviews": False,
            "required_approving_review_count": policy["required_approving_review_count"],
            "require_last_push_approval": False,
        },
        "restrictions": None,
        "required_linear_history": policy["required_linear_history"],
        "allow_force_pushes": policy["allow_force_pushes"],
        "allow_deletions": policy["allow_deletions"],
        "required_conversation_resolution": policy["require_conversation_resolution"],
    }


def _enabled(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("enabled"))
    return bool(value)


def audit_observed(policy: dict[str, Any], observed: dict[str, Any] | None) -> AuditResult:
    if observed is None:
        return AuditResult("DRIFT", ("branch_unprotected",), {"protected": False})

    drift: list[str] = []
    checks = observed.get("required_status_checks") or {}
    observed_contexts: set[str] = set(checks.get("contexts") or [])
    for item in checks.get("checks") or []:
        if isinstance(item, dict) and isinstance(item.get("context"), str):
            observed_contexts.add(item["context"])
    required_contexts = set(policy["required_status_checks"]["contexts"])
    missing = sorted(required_contexts - observed_contexts)
    if missing:
        drift.append("missing_required_status_checks:" + ",".join(missing))
    if bool(checks.get("strict")) is not policy["required_status_checks"]["strict"]:
        drift.append("strict_status_checks_mismatch")

    reviews = observed.get("required_pull_request_reviews")
    if policy["required_pull_request"] and not isinstance(reviews, dict):
        drift.append("pull_request_requirement_missing")
    elif isinstance(reviews, dict):
        if int(reviews.get("required_approving_review_count", -1)) != policy[
            "required_approving_review_count"
        ]:
            drift.append("required_approving_review_count_mismatch")
        if bool(reviews.get("dismiss_stale_reviews")) is not policy["dismiss_stale_reviews"]:
            drift.append("dismiss_stale_reviews_mismatch")

    if _enabled(observed.get("enforce_admins")) is not policy["enforce_admins"]:
        drift.append("enforce_admins_mismatch")
    if _enabled(observed.get("required_conversation_resolution")) is not policy[
        "require_conversation_resolution"
    ]:
        drift.append("conversation_resolution_mismatch")
    if _enabled(observed.get("allow_force_pushes")) is not policy["allow_force_pushes"]:
        drift.append("force_push_policy_mismatch")
    if _enabled(observed.get("allow_deletions")) is not policy["allow_deletions"]:
        drift.append("deletion_policy_mismatch")

    return AuditResult("CONVERGED" if not drift else "DRIFT", tuple(drift), observed)


def _request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    accept: str = "application/vnd.github+json",
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", accept)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "centinal26-governance-controller")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        payload: Any = None
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw.decode("utf-8", errors="replace")
        return exc.code, payload


def fetch_protection(policy: dict[str, Any], token: str) -> dict[str, Any] | None:
    url = f"{API}/repos/{policy['repository']}/branches/{policy['branch']}/protection"
    status, payload = _request("GET", url, token)
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError(f"protection readback failed: HTTP {status}: {payload}")
    if not isinstance(payload, dict):
        raise TypeError("protection readback was not a JSON object")
    return payload


def enforce_protection(policy: dict[str, Any], token: str) -> AuditResult:
    url = f"{API}/repos/{policy['repository']}/branches/{policy['branch']}/protection"
    status, payload = _request("PUT", url, token, protection_payload(policy))
    if status != 200:
        raise RuntimeError(f"protection mutation failed: HTTP {status}: {payload}")
    return audit_observed(policy, fetch_protection(policy, token))


def audit_push_provenance(repository: str, sha: str, token: str) -> dict[str, Any]:
    url = f"{API}/repos/{repository}/commits/{sha}/pulls"
    status, payload = _request(
        "GET",
        url,
        token,
        accept="application/vnd.github+json",
    )
    if status != 200:
        raise RuntimeError(f"commit/PR provenance read failed: HTTP {status}: {payload}")
    pulls = payload if isinstance(payload, list) else []
    merged_to_main = [
        item
        for item in pulls
        if isinstance(item, dict)
        and item.get("merged_at")
        and isinstance(item.get("base"), dict)
        and item["base"].get("ref") == "main"
    ]
    return {
        "schema": "automation.main_push_provenance/v1",
        "repository": repository,
        "sha": sha,
        "associated_pull_requests": [item.get("number") for item in merged_to_main],
        "qualified_pr_path_observed": bool(merged_to_main),
        "status": "PASS" if merged_to_main else "UNQUALIFIED_DIRECT_PUSH_OBSERVED",
    }


def _write(path: str | None, value: dict[str, Any]) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    print(text, end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policy",
        default=str(ROOT / "automation/governance/main_branch_protection.json"),
    )
    parser.add_argument(
        "--mode",
        choices=("validate-policy", "audit", "enforce", "audit-push"),
        required=True,
    )
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--sha")
    parser.add_argument("--output")
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args()

    policy = _load_policy(args.policy)
    if args.mode == "validate-policy":
        _write(args.output, {"schema": policy["schema"], "status": "PASS"})
        return

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise SystemExit(f"missing token environment variable: {args.token_env}")

    if args.mode == "audit-push":
        if not args.sha:
            raise SystemExit("--sha is required for audit-push")
        report = audit_push_provenance(policy["repository"], args.sha, token)
        _write(args.output, report)
        if args.fail_on_drift and report["status"] != "PASS":
            raise SystemExit(2)
        return

    if args.mode == "enforce":
        result = enforce_protection(policy, token)
    else:
        result = audit_observed(policy, fetch_protection(policy, token))

    report = {
        "schema": "automation.main_branch_protection_audit/v1",
        "repository": policy["repository"],
        "branch": policy["branch"],
        "tracker_issue": policy["tracker_issue"],
        "status": result.status,
        "drift": list(result.drift),
        "server_readback_observed": result.observed,
        "workflow_substitution_allowed": False,
        "physical_evidence_inferred": False,
        "deployment_authorization_inferred": False,
    }
    _write(args.output, report)
    if args.fail_on_drift and not result.converged:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
