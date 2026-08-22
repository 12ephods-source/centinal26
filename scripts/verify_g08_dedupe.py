"""Independent black-box verifier for account goal G08.

This verifier does not import the Dedupe implementation modules. It invokes their public
CLIs as subprocesses, constructs its own challenge cases, and evaluates observable
outputs against the G08 success criteria.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_CLI = ROOT / "scripts" / "structured_semantic_dedupe.py"
STORE_CLI = ROOT / "scripts" / "canonical_store.py"


class VerificationFailure(RuntimeError):
    """Raised when an independently evaluated G08 invariant fails."""


def _claim(
    object_id: str,
    value: Any,
    statement: str,
    *,
    exclusive: bool = True,
) -> dict[str, Any]:
    nibble = format((sum(ord(char) for char in object_id) % 15) + 1, "x")
    payload: dict[str, Any] = {
        "statement": statement,
        "subject_ids": ["device:independent-alpha"],
        "predicate": "security_state",
        "object_value": value,
    }
    if exclusive:
        payload["comparison_mode"] = "EXCLUSIVE_VALUE"
    return {
        "object_id": object_id,
        "schema_version": "1.0.0",
        "type": "CLAIM",
        "subtype": None,
        "content_hash": "sha256:" + nibble * 64,
        "identity_hash": None,
        "created_at": "2026-08-22T00:00:00Z",
        "observed_at": "2026-08-22T00:00:00Z",
        "ingested_at": "2026-08-22T00:00:01Z",
        "modified_at_source": None,
        "source_id": "independent-g08-verifier",
        "parent_ids": [],
        "related_ids": [],
        "status": "CANONICAL",
        "epistemic_status": "OBSERVED",
        "verification_status": "UNVERIFIED",
        "confidence": 1.0,
        "authority_class": "AUTHORITATIVE_RECORD",
        "authoritative": True,
        "provenance_ids": [],
        "tag_ids": [],
        "project_ids": ["dedupe-organizer"],
        "payload": payload,
        "extensions": {},
    }


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        raise VerificationFailure(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationFailure(f"expected object JSON in {path}")
    return value


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def verify() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        source_path = tmpdir / "source.json"
        enriched_path = tmpdir / "enriched.json"
        rerun_path = tmpdir / "rerun.json"
        db_path = tmpdir / "canonical.db"

        source = {
            "objects": [
                _claim("obj_verify_a", "SAFE", "first wording"),
                _claim("obj_verify_b", "SAFE", "different prose"),
                _claim("obj_verify_c", "COMPROMISED", "conflicting value"),
            ],
            "provenance_events": [],
            "filter_decisions": [],
        }
        source_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")

        _run(str(SEMANTIC_CLI), str(source_path), "--output", str(enriched_path))
        enriched = _load(enriched_path)

        source_ids = {obj["object_id"] for obj in source["objects"]}
        output_ids = {obj["object_id"] for obj in enriched.get("objects", [])}
        _assert(source_ids <= output_ids, "source claims were not all preserved")
        _assert(enriched.get("filter_decisions") == [], "semantic derivation created filter decisions")

        duplicates = [obj for obj in enriched["objects"] if obj.get("type") == "DUPLICATE_GROUP"]
        contradictions = [obj for obj in enriched["objects"] if obj.get("type") == "CONTRADICTION"]
        _assert(len(duplicates) == 1, f"expected one duplicate group, got {len(duplicates)}")
        _assert(len(contradictions) == 1, f"expected one contradiction, got {len(contradictions)}")

        duplicate = duplicates[0]
        _assert(
            duplicate["payload"]["member_ids"] == ["obj_verify_a", "obj_verify_b"],
            "structured-equivalent claims were not grouped exactly",
        )
        _assert(duplicate.get("authoritative") is False, "duplicate group became authoritative")
        _assert(duplicate["payload"].get("deletion_authority") is False, "deletion authority appeared")

        contradiction = contradictions[0]
        _assert(
            contradiction["payload"]["member_ids"]
            == ["obj_verify_a", "obj_verify_b", "obj_verify_c"],
            "exclusive disagreement did not preserve every conflicting claim",
        )
        _assert(
            contradiction["payload"].get("resolution_status") == "UNRESOLVED",
            "contradiction was silently resolved",
        )
        _assert(contradiction["payload"].get("winner_id") is None, "a contradiction winner was invented")
        _assert(contradiction.get("authoritative") is False, "contradiction became authoritative")

        provenance_by_id = {
            event["provenance_event_id"]: event for event in enriched.get("provenance_events", [])
        }
        for derived in (*duplicates, *contradictions):
            provenance_ids = derived.get("provenance_ids", [])
            _assert(len(provenance_ids) == 1, "derived relationship lacks one explicit provenance edge")
            event = provenance_by_id.get(provenance_ids[0])
            _assert(event is not None, "derived relationship points to missing provenance")
            _assert(derived["object_id"] in event["output_ids"], "provenance omits derived output")
            _assert(set(event["input_ids"]) == set(derived["payload"]["member_ids"]), "provenance inputs do not match members")

        _run(str(SEMANTIC_CLI), str(enriched_path), "--output", str(rerun_path))
        _assert(_load(rerun_path) == enriched, "semantic enrichment is not idempotent")

        nonexclusive_path = tmpdir / "nonexclusive.json"
        nonexclusive_out = tmpdir / "nonexclusive-out.json"
        nonexclusive = {
            "objects": [
                _claim("obj_verify_x", 1, "value one", exclusive=False),
                _claim("obj_verify_y", 2, "value two", exclusive=False),
            ],
            "provenance_events": [],
            "filter_decisions": [],
        }
        nonexclusive_path.write_text(json.dumps(nonexclusive, indent=2) + "\n", encoding="utf-8")
        _run(str(SEMANTIC_CLI), str(nonexclusive_path), "--output", str(nonexclusive_out))
        nonexclusive_result = _load(nonexclusive_out)
        _assert(
            not [obj for obj in nonexclusive_result["objects"] if obj.get("type") == "CONTRADICTION"],
            "non-exclusive disagreement was silently promoted to contradiction",
        )

        first = json.loads(_run(str(STORE_CLI), "--db", str(db_path), "ingest", str(source_path)).stdout)
        second = json.loads(_run(str(STORE_CLI), "--db", str(db_path), "ingest", str(enriched_path)).stdout)
        third = json.loads(_run(str(STORE_CLI), "--db", str(db_path), "ingest", str(enriched_path)).stdout)
        _assert(first == {"filter_decisions": 0, "objects": 3, "provenance_events": 0}, "source ingest mismatch")
        _assert(second == {"filter_decisions": 0, "objects": 2, "provenance_events": 2}, "derived ingest mismatch")
        _assert(third == {"filter_decisions": 0, "objects": 0, "provenance_events": 0}, "re-ingest was not idempotent")

        _run(str(STORE_CLI), "--db", str(db_path), "rebuild-projection")
        stats = json.loads(_run(str(STORE_CLI), "--db", str(db_path), "stats").stdout)
        _assert(stats["canonical_objects"] == 5, "canonical object count changed unexpectedly")
        _assert(stats["object_projection"] == 5, "rebuildable projection count mismatch")

        return {
            "schema": "g08-independent-verification/v1",
            "verdict": "VERIFIED",
            "scope": "software semantics only",
            "criteria": {
                "typed_immutable_objects": "PASS",
                "semantic_dedupe_without_automatic_deletion": "PASS",
                "contradiction_preservation": "PASS",
                "rebuildable_projections": "PASS",
                "idempotent_ingestion": "PASS",
                "nonexclusive_fail_closed": "PASS",
                "explicit_provenance": "PASS",
            },
            "limits": [
                "does not establish semantic truth of claims",
                "does not establish forensic attribution",
                "does not establish scientific validity",
                "does not establish physical Android execution",
            ],
        }


def main() -> int:
    try:
        result = verify()
    except (VerificationFailure, OSError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": "g08-independent-verification/v1", "verdict": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
