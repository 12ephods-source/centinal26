"""Fail-closed structural and relational validation for governance bundles."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _fields(names: str) -> frozenset[str]:
    return frozenset(names.split())


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = frozenset({"PASS", "REVIEW", "FAIL"})
CLAIM_STATUSES = frozenset(
    {"VERIFIED", "REPORTED", "DERIVED", "PROPOSED", "FAILED", "SUPERSEDED", "UNKNOWN"}
)
RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
BUNDLE_SCHEMA = "centinal26-governance-bundle-v1"
COLLECTIONS = (
    "authorizations",
    "evidence",
    "operations",
    "claims",
    "promotions",
    "terminal_events",
)
BUNDLE_FIELDS = frozenset({"schema", *COLLECTIONS})
AUTH_FIELDS = _fields(
    "schema authorization_id issuer subject capability scope risk_class "
    "issued_at expires_at signature"
)
EVIDENCE_FIELDS = _fields(
    "schema evidence_id sha256 source_type created_at immutable"
)
OPERATION_FIELDS = _fields(
    "schema operation_id actor authorization_id capability_id scope risk_class preconditions "
    "postconditions destructive preservation_evidence_refs"
)
CLAIM_FIELDS = _fields(
    "schema claim_id status proposition evidence_refs uncertainty"
)
PROMOTION_FIELDS = _fields(
    "schema promotion_id operation_id executor verifier authorized safe "
    "traceable verified evidence_refs"
)
TERMINAL_FIELDS = _fields(
    "schema terminal_event_id operation_id status evidence_refs"
)


@dataclass(frozen=True, order=True)
class Violation:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _add(violations: list[Violation], code: str, path: str, message: str) -> None:
    violations.append(Violation(code, path, message))


def _check(
    condition: bool,
    violations: list[Violation],
    code: str,
    path: str,
    message: str,
) -> None:
    if not condition:
        _add(violations, code, path, message)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


def _record(
    value: Any,
    *,
    path: str,
    prefix: str,
    noun: str,
    schema: str,
    fields: frozenset[str],
    violations: list[Violation],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _add(violations, f"{prefix}_OBJECT_REQUIRED", path, f"{noun} must be an object")
        return None
    for field in sorted(fields - value.keys(), key=str):
        _add(violations, "FIELD_REQUIRED", f"{path}.{field}", f"{field} is required")
    for field in sorted(value.keys() - fields, key=str):
        _add(
            violations,
            "ADDITIONAL_PROPERTY_FORBIDDEN",
            f"{path}.{field}",
            f"{field} is not allowed by the object schema",
        )
    if "schema" in value:
        _check(
            value.get("schema") == schema,
            violations,
            "SCHEMA_VERSION_INVALID",
            f"{path}.schema",
            f"schema must be {schema}",
        )
    return value


def _text(
    item: dict[str, Any],
    key: str,
    path: str,
    violations: list[Violation],
    code: str,
) -> str | None:
    value = item.get(key)
    if isinstance(value, str) and value:
        return value
    _add(violations, code, f"{path}.{key}", f"{key} must be a non-empty string")
    return None


def _mapping(
    item: dict[str, Any],
    key: str,
    path: str,
    violations: list[Violation],
    code: str,
) -> dict[str, Any] | None:
    value = item.get(key)
    if isinstance(value, dict):
        return value
    _add(violations, code, f"{path}.{key}", f"{key} must be an object")
    return None


def _enum(
    item: dict[str, Any],
    key: str,
    allowed: set[str] | frozenset[str] | dict[str, int],
    path: str,
    violations: list[Violation],
    code: str,
) -> str | None:
    value = item.get(key)
    if isinstance(value, str) and value in allowed:
        return value
    _add(violations, code, f"{path}.{key}", f"{key} is outside its closed set")
    return None


def _timestamp(
    item: dict[str, Any],
    key: str,
    path: str,
    violations: list[Violation],
    code: str,
) -> datetime | None:
    value = item.get(key)
    if isinstance(value, str):
        try:
            return _parse_time(value)
        except (TypeError, ValueError):
            pass
    _add(
        violations,
        code,
        f"{path}.{key}",
        f"{key} must be an offset-aware ISO-8601 timestamp",
    )
    return None


def _strings(
    item: dict[str, Any],
    key: str,
    path: str,
    violations: list[Violation],
    code: str,
    *,
    min_items: int = 0,
) -> list[str] | None:
    value = item.get(key)
    if not isinstance(value, list):
        _add(violations, code, f"{path}.{key}", f"{key} must be an array")
        return None
    valid = len(value) >= min_items
    if not valid:
        _add(violations, code, f"{path}.{key}", f"{key} requires {min_items} item(s)")
    result: list[str] = []
    for index, entry in enumerate(value):
        if isinstance(entry, str) and entry:
            result.append(entry)
        else:
            _add(
                violations,
                code,
                f"{path}.{key}[{index}]",
                "array entries must be non-empty strings",
            )
            valid = False
    if len(result) != len(set(result)):
        _add(violations, code, f"{path}.{key}", "array entries must be unique")
        valid = False
    return result if valid else None


def _index_unique(
    items: list[Any],
    id_field: str,
    collection: str,
    violations: list[Violation],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    singular = collection.removesuffix("s").upper()
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = item.get(id_field)
        if not isinstance(value, str) or not value:
            continue
        if value in index:
            _add(
                violations,
                f"DUPLICATE_{singular}_ID",
                f"{collection}[{position}].{id_field}",
                f"{id_field} must be unique within {collection}",
            )
        else:
            index[value] = item
    return index


def _refs_exist(
    refs: list[str] | None,
    index: dict[str, dict[str, Any]],
    path: str,
    violations: list[Violation],
    code: str,
) -> bool:
    if refs is None:
        return False
    valid = True
    for position, ref in enumerate(refs):
        if ref not in index:
            _add(violations, code, f"{path}[{position}]", "reference does not exist")
            valid = False
    return valid


def validate_bundle(bundle: Any, *, now: datetime | None = None) -> list[Violation]:
    """Validate a standalone governance bundle.

    The boundary validates structure, relationships, declarations, and caller-supplied
    attestations. It does not intercept execution, authenticate signatures, or evaluate
    the truth of declared conditions. Replay callers must inject an offset-aware time.
    """

    violations: list[Violation] = []
    if not isinstance(bundle, dict):
        return [Violation("BUNDLE_OBJECT_REQUIRED", "$", "bundle root must be an object")]
    if now is None:
        validation_time = datetime.now(UTC)
    elif not isinstance(now, datetime) or now.tzinfo is None:
        return [Violation("REPLAY_TIME_INVALID", "$", "validation time must be offset-aware")]
    else:
        validation_time = now.astimezone(UTC)

    for field in sorted(BUNDLE_FIELDS - bundle.keys(), key=str):
        _add(violations, "BUNDLE_FIELD_REQUIRED", f"$.{field}", f"{field} is required")
    for field in sorted(bundle.keys() - BUNDLE_FIELDS, key=str):
        _add(
            violations,
            "BUNDLE_ADDITIONAL_PROPERTY_FORBIDDEN",
            f"$.{field}",
            f"{field} is not allowed by the bundle schema",
        )
    if "schema" in bundle:
        _check(
            bundle.get("schema") == BUNDLE_SCHEMA,
            violations,
            "BUNDLE_SCHEMA_INVALID",
            "$.schema",
            f"schema must be {BUNDLE_SCHEMA}",
        )

    collections: dict[str, list[Any]] = {}
    for name in COLLECTIONS:
        value = bundle.get(name)
        if isinstance(value, list):
            collections[name] = value
        else:
            if name in bundle:
                _add(
                    violations,
                    "BUNDLE_COLLECTION_ARRAY_REQUIRED",
                    f"$.{name}",
                    f"{name} must be an array",
                )
            collections[name] = []

    authorizations = collections["authorizations"]
    evidence_items = collections["evidence"]
    operations = collections["operations"]
    claims = collections["claims"]
    promotions = collections["promotions"]
    terminal_events = collections["terminal_events"]

    for index, value in enumerate(authorizations):
        path = f"authorizations[{index}]"
        item = _record(
            value,
            path=path,
            prefix="AUTH",
            noun="authorization",
            schema="centinal26-authorization-v1",
            fields=AUTH_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "authorization_id", path, violations, "AUTHORIZATION_ID_INVALID")
        issuer = _text(item, "issuer", path, violations, "AUTH_ISSUER_REQUIRED")
        subject = _text(item, "subject", path, violations, "AUTH_SUBJECT_REQUIRED")
        _check(
            issuer is None or subject is None or issuer != subject,
            violations,
            "SELF_AUTHORIZATION_FORBIDDEN",
            path,
            "authorization issuer cannot authorize itself",
        )
        _text(item, "capability", path, violations, "AUTH_CAPABILITY_REQUIRED")
        _mapping(item, "scope", path, violations, "AUTH_SCOPE_INVALID")
        _enum(item, "risk_class", RISK_RANK, path, violations, "AUTH_RISK_INVALID")
        issued = _timestamp(item, "issued_at", path, violations, "AUTH_ISSUED_AT_INVALID")
        expires = _timestamp(item, "expires_at", path, violations, "AUTH_EXPIRY_INVALID")
        if issued is not None:
            _check(
                issued <= validation_time,
                violations,
                "AUTH_NOT_YET_VALID",
                f"{path}.issued_at",
                "authorization is not yet valid",
            )
        if expires is not None:
            _check(
                expires > validation_time,
                violations,
                "AUTH_EXPIRED",
                f"{path}.expires_at",
                "authorization is expired",
            )
        if issued is not None and expires is not None:
            _check(
                issued < expires,
                violations,
                "AUTH_TIME_RANGE_INVALID",
                path,
                "issued_at must precede expires_at",
            )
        _text(item, "signature", path, violations, "AUTH_SIGNATURE_REQUIRED")

    for index, value in enumerate(evidence_items):
        path = f"evidence[{index}]"
        item = _record(
            value,
            path=path,
            prefix="EVIDENCE",
            noun="evidence",
            schema="centinal26-governance-evidence-v1",
            fields=EVIDENCE_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "evidence_id", path, violations, "EVIDENCE_ID_INVALID")
        digest = item.get("sha256")
        _check(
            isinstance(digest, str) and bool(SHA256_RE.fullmatch(digest)),
            violations,
            "EVIDENCE_SHA256_INVALID",
            f"{path}.sha256",
            "sha256 must be 64 lowercase hex characters",
        )
        _check(
            item.get("immutable") is True,
            violations,
            "EVIDENCE_NOT_IMMUTABLE",
            f"{path}.immutable",
            "evidence must be explicitly immutable",
        )
        _enum(
            item,
            "source_type",
            {"SOURCE", "DERIVED", "SUMMARY"},
            path,
            violations,
            "EVIDENCE_SOURCE_TYPE_INVALID",
        )
        created = _timestamp(
            item, "created_at", path, violations, "EVIDENCE_CREATED_AT_INVALID"
        )
        if created is not None:
            _check(
                created <= validation_time,
                violations,
                "EVIDENCE_FROM_FUTURE",
                f"{path}.created_at",
                "evidence must exist by validation time",
            )

    authorization_index = _index_unique(
        authorizations, "authorization_id", "authorizations", violations
    )
    evidence_index = _index_unique(evidence_items, "evidence_id", "evidence", violations)

    for index, value in enumerate(operations):
        path = f"operations[{index}]"
        item = _record(
            value,
            path=path,
            prefix="OPERATION",
            noun="operation",
            schema="centinal26-operation-v1",
            fields=OPERATION_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "operation_id", path, violations, "OPERATION_ID_INVALID")
        actor = _text(item, "actor", path, violations, "OPERATION_ACTOR_INVALID")
        auth_id = _text(
            item,
            "authorization_id",
            path,
            violations,
            "OPERATION_AUTHORIZATION_ID_INVALID",
        )
        capability = _text(
            item, "capability_id", path, violations, "OPERATION_CAPABILITY_INVALID"
        )
        scope = _mapping(item, "scope", path, violations, "OPERATION_SCOPE_INVALID")
        risk = _enum(
            item, "risk_class", RISK_RANK, path, violations, "OPERATION_RISK_INVALID"
        )
        _strings(item, "preconditions", path, violations, "PRECONDITIONS_INVALID")
        _strings(
            item,
            "postconditions",
            path,
            violations,
            "POSTCONDITIONS_REQUIRED",
            min_items=1,
        )
        destructive = item.get("destructive")
        _check(
            isinstance(destructive, bool),
            violations,
            "DESTRUCTIVE_FLAG_INVALID",
            f"{path}.destructive",
            "destructive must be a boolean",
        )
        preservation_refs = _strings(
            item,
            "preservation_evidence_refs",
            path,
            violations,
            "PRESERVATION_REFS_INVALID",
        )
        refs_valid = _refs_exist(
            preservation_refs,
            evidence_index,
            f"{path}.preservation_evidence_refs",
            violations,
            "PRESERVATION_EVIDENCE_UNKNOWN",
        )

        authorization = authorization_index.get(auth_id) if auth_id is not None else None
        if auth_id is not None:
            _check(
                authorization is not None,
                violations,
                "AUTHORIZATION_REQUIRED",
                f"{path}.authorization_id",
                "operation must reference an existing authorization",
            )
        if authorization is not None:
            _check(
                actor is None or authorization.get("subject") == actor,
                violations,
                "AUTH_SUBJECT_MISMATCH",
                path,
                "authorization subject must equal operation actor",
            )
            _check(
                actor is None or authorization.get("issuer") != actor,
                violations,
                "SELF_AUTHORIZATION_FORBIDDEN",
                path,
                "operation actor cannot be its own authorization issuer",
            )
            _check(
                capability is None or authorization.get("capability") == capability,
                violations,
                "AUTH_CAPABILITY_MISMATCH",
                path,
                "authorization capability must match operation capability",
            )
            auth_scope = authorization.get("scope")
            if scope is not None and isinstance(auth_scope, dict):
                _check(
                    auth_scope == scope,
                    violations,
                    "AUTH_SCOPE_MISMATCH",
                    path,
                    "authorization scope must exactly match operation scope",
                )
            auth_risk = authorization.get("risk_class")
            if risk is not None and isinstance(auth_risk, str) and auth_risk in RISK_RANK:
                _check(
                    RISK_RANK[auth_risk] >= RISK_RANK[risk],
                    violations,
                    "AUTH_RISK_INSUFFICIENT",
                    path,
                    "authorization risk class is weaker than operation risk class",
                )
        if destructive is True:
            _check(
                bool(preservation_refs) and refs_valid,
                violations,
                "PRESERVATION_REQUIRED_BEFORE_DESTRUCTIVE_ACTION",
                f"{path}.preservation_evidence_refs",
                "destructive operations require evidence present by validation time",
            )

    operation_index = _index_unique(operations, "operation_id", "operations", violations)

    for index, value in enumerate(claims):
        path = f"claims[{index}]"
        item = _record(
            value,
            path=path,
            prefix="CLAIM",
            noun="claim",
            schema="centinal26-claim-v1",
            fields=CLAIM_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "claim_id", path, violations, "CLAIM_ID_INVALID")
        status = _enum(
            item, "status", CLAIM_STATUSES, path, violations, "CLAIM_STATUS_INVALID"
        )
        _text(item, "proposition", path, violations, "CLAIM_PROPOSITION_INVALID")
        uncertainty = item.get("uncertainty")
        uncertainty_valid = (
            "uncertainty" in item
            and not isinstance(uncertainty, bool)
            and (uncertainty is None or isinstance(uncertainty, (str, int, float)))
        )
        _check(
            uncertainty_valid,
            violations,
            "CLAIM_UNCERTAINTY_REQUIRED",
            f"{path}.uncertainty",
            "uncertainty must be a string, number, or null",
        )
        refs = _strings(
            item, "evidence_refs", path, violations, "CLAIM_EVIDENCE_REFS_INVALID"
        )
        refs_valid = _refs_exist(
            refs,
            evidence_index,
            f"{path}.evidence_refs",
            violations,
            "CLAIM_EVIDENCE_UNKNOWN",
        )
        if status in {"DERIVED", "VERIFIED"}:
            _check(
                bool(refs) and refs_valid,
                violations,
                "CLAIM_PROVENANCE_REQUIRED",
                f"{path}.evidence_refs",
                "derived and verified claims require existing evidence",
            )
            if refs and refs_valid:
                only_summaries = all(
                    evidence_index[ref].get("source_type") == "SUMMARY" for ref in refs
                )
                _check(
                    not only_summaries,
                    violations,
                    "SUMMARY_CANNOT_REPLACE_SOURCE",
                    f"{path}.evidence_refs",
                    "a summary alone cannot substantiate this claim status",
                )

    _index_unique(claims, "claim_id", "claims", violations)

    for index, value in enumerate(promotions):
        path = f"promotions[{index}]"
        item = _record(
            value,
            path=path,
            prefix="PROMOTION",
            noun="promotion",
            schema="centinal26-promotion-v1",
            fields=PROMOTION_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "promotion_id", path, violations, "PROMOTION_ID_INVALID")
        operation_id = _text(
            item,
            "operation_id",
            path,
            violations,
            "PROMOTION_OPERATION_ID_INVALID",
        )
        executor = _text(item, "executor", path, violations, "PROMOTION_EXECUTOR_INVALID")
        verifier = _text(item, "verifier", path, violations, "PROMOTION_VERIFIER_INVALID")
        _check(
            executor is None or verifier is None or executor != verifier,
            violations,
            "INDEPENDENT_VERIFICATION_REQUIRED",
            f"{path}.verifier",
            "promotion verifier must differ from executor",
        )
        operation = operation_index.get(operation_id) if operation_id is not None else None
        if operation_id is not None:
            _check(
                operation is not None,
                violations,
                "PROMOTION_OPERATION_UNKNOWN",
                f"{path}.operation_id",
                "promotion must reference an existing operation",
            )
        if operation is not None and executor is not None:
            _check(
                operation.get("actor") == executor,
                violations,
                "PROMOTION_EXECUTOR_MISMATCH",
                f"{path}.executor",
                "promotion executor must match operation actor",
            )
        for gate in ("authorized", "safe", "traceable", "verified"):
            _check(
                item.get(gate) is True,
                violations,
                f"PROMOTION_{gate.upper()}_REQUIRED",
                f"{path}.{gate}",
                f"promotion requires {gate}=true",
            )
        refs = _strings(
            item,
            "evidence_refs",
            path,
            violations,
            "PROMOTION_EVIDENCE_REFS_INVALID",
            min_items=1,
        )
        refs_valid = _refs_exist(
            refs,
            evidence_index,
            f"{path}.evidence_refs",
            violations,
            "PROMOTION_EVIDENCE_UNKNOWN",
        )
        _check(
            bool(refs) and refs_valid,
            violations,
            "PROMOTION_EVIDENCE_REQUIRED",
            f"{path}.evidence_refs",
            "promotion requires existing evidence",
        )

    _index_unique(promotions, "promotion_id", "promotions", violations)

    for index, value in enumerate(terminal_events):
        path = f"terminal_events[{index}]"
        item = _record(
            value,
            path=path,
            prefix="TERMINAL",
            noun="terminal event",
            schema="centinal26-terminal-event-v1",
            fields=TERMINAL_FIELDS,
            violations=violations,
        )
        if item is None:
            continue
        _text(item, "terminal_event_id", path, violations, "TERMINAL_EVENT_ID_INVALID")
        operation_id = _text(
            item,
            "operation_id",
            path,
            violations,
            "TERMINAL_OPERATION_ID_INVALID",
        )
        if operation_id is not None:
            _check(
                operation_id in operation_index,
                violations,
                "TERMINAL_OPERATION_UNKNOWN",
                f"{path}.operation_id",
                "terminal event must reference an existing operation",
            )
        _enum(item, "status", TERMINAL_STATES, path, violations, "TERMINAL_STATE_INVALID")
        refs = _strings(
            item,
            "evidence_refs",
            path,
            violations,
            "TERMINAL_EVIDENCE_REFS_INVALID",
            min_items=1,
        )
        _refs_exist(
            refs,
            evidence_index,
            f"{path}.evidence_refs",
            violations,
            "TERMINAL_EVIDENCE_UNKNOWN",
        )

    _index_unique(terminal_events, "terminal_event_id", "terminal_events", violations)
    return sorted(set(violations))


def _report(violations: list[Violation]) -> dict[str, Any]:
    return {
        "schema": "centinal26-governance-report-v1",
        "valid": not violations,
        "violation_count": len(violations),
        "violations": [item.as_dict() for item in violations],
    }


def validate_file(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return _report(
            [
                Violation(
                    "JSON_INVALID",
                    "$",
                    f"invalid JSON at line {error.lineno}, column {error.colno}",
                )
            ]
        )
    return _report(validate_bundle(payload, now=now))


def main() -> None:
    parser = argparse.ArgumentParser(prog="centinal26-governance")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--at", dest="at_time", help="ISO-8601 validation/replay time")
    args = parser.parse_args()
    if args.at_time:
        try:
            at_time = _parse_time(args.at_time)
        except (TypeError, ValueError):
            report = _report(
                [
                    Violation(
                        "REPLAY_TIME_INVALID",
                        "$.at_time",
                        "--at must be an offset-aware ISO-8601 timestamp",
                    )
                ]
            )
        else:
            report = validate_file(args.bundle.expanduser(), now=at_time)
    else:
        report = validate_file(args.bundle.expanduser())
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["valid"] else 2)


if __name__ == "__main__":
    main()
