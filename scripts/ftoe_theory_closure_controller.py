from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "physics/ftoe/THEORY_CLOSURE_LEDGER_v1.json"
ALLOWED_STATUS = {"PASS", "REVIEW", "FAIL", "BLOCKED", "OPEN"}
ALLOWED_EXECUTION = {"READY", "MISSING_SOURCE", "WAITING_EXTERNAL", "BLOCKED"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def evaluate(ledger_path: Path) -> tuple[dict, list[str]]:
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if data.get("schema") != "frost.ftoe.theory_closure_ledger/v1":
        errors.append("unexpected ledger schema")
    if data.get("mode") not in {"DEVELOPMENT", "CONFIRMATORY"}:
        errors.append("mode must be DEVELOPMENT or CONFIRMATORY")

    policy = data.get("policy", {})
    required_policy = {
        "freeze_evidence_and_history",
        "allow_versioned_development_changes",
        "confirmatory_versions_are_immutable",
        "no_retuning_after_confirmatory_outcome",
        "software_pass_is_not_scientific_pass",
    }
    missing_policy = sorted(required_policy - set(policy))
    if missing_policy:
        errors.append(f"missing policy keys: {', '.join(missing_policy)}")

    source_results = []
    for source in data.get("source_records", []):
        path = ROOT / source["path"]
        row = {"path": source["path"], "git_blob_sha": source.get("git_blob_sha")}
        if not path.exists():
            row["present"] = False
            errors.append(f"missing source record: {source['path']}")
        else:
            row["present"] = True
            row["sha256"] = sha256(path)
        source_results.append(row)

    items = data.get("closure_items", [])
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)):
        errors.append("duplicate closure item id")

    for item in items:
        if item.get("status") not in ALLOWED_STATUS:
            errors.append(f"{item.get('id')}: invalid status")
        if item.get("execution_state") not in ALLOWED_EXECUTION:
            errors.append(f"{item.get('id')}: invalid execution_state")
        if not str(item.get("smallest_next_action", "")).strip():
            errors.append(f"{item.get('id')}: missing smallest_next_action")
        if item.get("status") == "PASS" and item.get("execution_state") != "READY":
            errors.append(f"{item.get('id')}: PASS cannot be based on unavailable execution/evidence")
        for evidence_path in item.get("evidence_paths", []):
            if not (ROOT / evidence_path).exists():
                errors.append(f"{item.get('id')}: missing evidence path {evidence_path}")

    ranked = sorted(items, key=lambda x: (x.get("priority", 10**9), x.get("id", "")))
    next_ready = next(
        (
            x
            for x in ranked
            if x.get("status") != "PASS" and x.get("execution_state") == "READY"
        ),
        None,
    )
    blocked_higher = [
        {"id": x["id"], "priority": x["priority"], "execution_state": x["execution_state"]}
        for x in ranked
        if next_ready
        and x.get("priority", 10**9) < next_ready.get("priority", 10**9)
        and x.get("status") != "PASS"
    ]

    result = {
        "ledger": str(ledger_path.relative_to(ROOT)),
        "ledger_sha256": sha256(ledger_path),
        "mode": data.get("mode"),
        "integrity_pass": not errors,
        "scientific_closure_complete": bool(items)
        and all(x.get("status") == "PASS" for x in items),
        "open_item_count": sum(1 for x in items if x.get("status") != "PASS"),
        "next_ready_item": next_ready,
        "higher_priority_blocked_items": blocked_higher,
        "source_records": source_results,
        "errors": errors,
    }
    return result, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--strict-integrity", action="store_true")
    args = parser.parse_args()

    ledger_path = args.ledger
    if not ledger_path.is_absolute():
        ledger_path = ROOT / ledger_path
    result, errors = evaluate(ledger_path)
    text = json.dumps(result, sort_keys=True, indent=2)
    print(text)
    if args.json_out:
        out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 1 if args.strict_integrity and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
