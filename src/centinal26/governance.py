from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = frozenset({"PASS", "REVIEW", "FAIL"})
CLAIM_STATUSES = frozenset(
    {"VERIFIED", "REPORTED", "DERIVED", "PROPOSED", "FAILED", "SUPERSEDED", "UNKNOWN"}
)
RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True, order=True)
class Violation:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


def _require(condition: bool, violations: list[Violation], code: str, path: str, message: str) -> None:
    if not condition:
        violations.append(Violation(code, path, message))


def validate_bundle(bundle: dict[str, Any], *, now: datetime | None = None) -> list[Violation]:
    """Validate deterministic Centinal26 governance invariants.

    The function is deliberately pure except for the optional clock input. Callers that
    require replay determinism must pass the event/replay time explicitly via ``now``.
    """

    violations: list[Violation] = []
    now = (now or datetime.now(UTC)).astimezone(UTC)

    authorizations = {
        item.get("authorization_id"): item
        for item in bundle.get("authorizations", [])
        if isinstance(item, dict) and isinstance(item.get("authorization_id"), str)
    }
    evidence = {
        item.get("evidence_id"): item
        for item in bundle.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }

    for idx, item in enumerate(bundle.get("evidence", [])):
        path = f"evidence[{idx}]"
        if not isinstance(item, dict):
            violations.append(Violation("EVIDENCE_OBJECT_REQUIRED", path, "evidence must be an object"))
            continue
        digest = item.get("sha256")
        _require(isinstance(digest, str) and bool(SHA256_RE.fullmatch(digest)), violations,
                 "EVIDENCE_SHA256_INVALID", f"{path}.sha256", "sha256 must be 64 lowercase hex characters")
        _require(item.get("immutable") is True, violations, "EVIDENCE_NOT_IMMUTABLE",
                 f"{path}.immutable", "evidence must be explicitly immutable")
        _require(item.get("source_type") in {"SOURCE", "DERIVED", "SUMMARY"}, violations,
                 "EVIDENCE_SOURCE_TYPE_INVALID", f"{path}.source_type",
                 "source_type must be SOURCE, DERIVED, or SUMMARY")

    for idx, auth in enumerate(bundle.get("authorizations", [])):
        path = f"authorizations[{idx}]"
        if not isinstance(auth, dict):
            violations.append(Violation("AUTH_OBJECT_REQUIRED", path, "authorization must be an object"))
            continue
        issuer = auth.get("issuer")
        subject = auth.get("subject")
        _require(isinstance(issuer, str) and bool(issuer), violations, "AUTH_ISSUER_REQUIRED",
                 f"{path}.issuer", "authorization issuer is required")
        _require(isinstance(subject, str) and bool(subject), violations, "AUTH_SUBJECT_REQUIRED",
                 f"{path}.subject", "authorization subject is required")
        _require(issuer != subject, violations, "SELF_AUTHORIZATION_FORBIDDEN", path,
                 "an authorization issuer cannot authorize itself")
        _require(auth.get("risk_class") in RISK_RANK, violations, "AUTH_RISK_INVALID",
                 f"{path}.risk_class", "risk_class must be LOW, MEDIUM, HIGH, or CRITICAL")
        try:
            expires = _parse_time(str(auth.get("expires_at")))
        except (TypeError, ValueError):
            violations.append(Violation("AUTH_EXPIRY_INVALID", f"{path}.expires_at",
                                        "expires_at must be an offset-aware ISO-8601 timestamp"))
        else:
            _require(expires > now, violations, "AUTH_EXPIRED", f"{path}.expires_at",
                     "authorization is expired at the validation time")

    for idx, op in enumerate(bundle.get("operations", [])):
        path = f"operations[{idx}]"
        if not isinstance(op, dict):
            violations.append(Violation("OPERATION_OBJECT_REQUIRED", path, "operation must be an object"))
            continue
        auth_id = op.get("authorization_id")
        auth = authorizations.get(auth_id)
        _require(auth is not None, violations, "AUTHORIZATION_REQUIRED", f"{path}.authorization_id",
                 "operation must reference an existing authorization")
        _require(isinstance(op.get("postconditions"), list) and len(op.get("postconditions", [])) > 0,
                 violations, "POSTCONDITIONS_REQUIRED", f"{path}.postconditions",
                 "postconditions must be declared before execution")
        _require(isinstance(op.get("preconditions"), list), violations, "PRECONDITIONS_REQUIRED",
                 f"{path}.preconditions", "preconditions must be explicitly declared")
        if auth is not None:
            _require(auth.get("subject") == op.get("actor"), violations, "AUTH_SUBJECT_MISMATCH", path,
                     "authorization subject must equal operation actor")
            _require(auth.get("issuer") != op.get("actor"), violations, "SELF_AUTHORIZATION_FORBIDDEN", path,
                     "operation actor cannot be its own authorization issuer")
            _require(auth.get("capability") == op.get("capability_id"), violations,
                     "AUTH_CAPABILITY_MISMATCH", path,
                     "authorization capability must match operation capability")
            required_risk = op.get("risk_class")
            if required_risk in RISK_RANK and auth.get("risk_class") in RISK_RANK:
                _require(RISK_RANK[auth["risk_class"]] >= RISK_RANK[required_risk], violations,
                         "AUTH_RISK_INSUFFICIENT", path,
                         "authorization risk class is weaker than operation risk class")
        if op.get("destructive") is True:
            refs = op.get("preservation_evidence_refs")
            valid_refs = isinstance(refs, list) and refs and all(ref in evidence for ref in refs)
            _require(bool(valid_refs), violations, "PRESERVATION_REQUIRED_BEFORE_DESTRUCTIVE_ACTION",
                     f"{path}.preservation_evidence_refs",
                     "destructive operations require existing preservation evidence")

    for idx, claim in enumerate(bundle.get("claims", [])):
        path = f"claims[{idx}]"
        if not isinstance(claim, dict):
            violations.append(Violation("CLAIM_OBJECT_REQUIRED", path, "claim must be an object"))
            continue
        status = claim.get("status")
        _require(status in CLAIM_STATUSES, violations, "CLAIM_STATUS_INVALID", f"{path}.status",
                 "claim status is not canonical")
        _require("uncertainty" in claim, violations, "CLAIM_UNCERTAINTY_REQUIRED", f"{path}.uncertainty",
                 "uncertainty must be represented explicitly")
        refs = claim.get("evidence_refs")
        if status in {"DERIVED", "VERIFIED"}:
            valid_refs = isinstance(refs, list) and refs and all(ref in evidence for ref in refs)
            _require(bool(valid_refs), violations, "CLAIM_PROVENANCE_REQUIRED", f"{path}.evidence_refs",
                     "derived and verified claims require existing evidence references")
            if valid_refs:
                only_summaries = all(evidence[ref].get("source_type") == "SUMMARY" for ref in refs)
                _require(not only_summaries, violations, "SUMMARY_CANNOT_REPLACE_SOURCE",
                         f"{path}.evidence_refs",
                         "a summary alone cannot substantiate a derived or verified claim")

    for idx, promotion in enumerate(bundle.get("promotions", [])):
        path = f"promotions[{idx}]"
        if not isinstance(promotion, dict):
            violations.append(Violation("PROMOTION_OBJECT_REQUIRED", path, "promotion must be an object"))
            continue
        for gate in ("authorized", "safe", "traceable", "verified"):
            _require(promotion.get(gate) is True, violations, f"PROMOTION_{gate.upper()}_REQUIRED",
                     f"{path}.{gate}", f"promotion requires {gate}=true")
        _require(promotion.get("independent_verifier") is True, violations,
                 "INDEPENDENT_VERIFICATION_REQUIRED", f"{path}.independent_verifier",
                 "promotion requires an independent verifier")
        refs = promotion.get("evidence_refs")
        _require(isinstance(refs, list) and bool(refs) and all(ref in evidence for ref in refs),
                 violations, "PROMOTION_EVIDENCE_REQUIRED", f"{path}.evidence_refs",
                 "promotion requires existing evidence references")

    for idx, terminal in enumerate(bundle.get("terminal_events", [])):
        path = f"terminal_events[{idx}]"
        if not isinstance(terminal, dict):
            violations.append(Violation("TERMINAL_OBJECT_REQUIRED", path, "terminal event must be an object"))
            continue
        _require(terminal.get("status") in TERMINAL_STATES, violations, "TERMINAL_STATE_INVALID",
                 f"{path}.status", "terminal status must be PASS, REVIEW, or FAIL")

    return sorted(set(violations))


def validate_file(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("governance bundle root must be a JSON object")
    violations = validate_bundle(payload, now=now)
    return {
        "schema": "centinal26-governance-report-v1",
        "valid": not violations,
        "violation_count": len(violations),
        "violations": [item.as_dict() for item in violations],
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="centinal26-governance")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--at", dest="at_time", help="ISO-8601 validation/replay time")
    args = parser.parse_args()
    at_time = _parse_time(args.at_time) if args.at_time else None
    report = validate_file(args.bundle.expanduser(), now=at_time)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["valid"] else 2)


if __name__ == "__main__":
    main()
