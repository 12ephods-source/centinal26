"""Fail-closed disposition gate for the current protected-I candidate.

A candidate with any mandatory admission subgate in FAIL state is itself FAIL for
admission. Downstream candidate-specific work must stop unless a separately
versioned successor repairs the failed mandatory gate. This does not kill the
broader mechanism class.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "physics" / "ftoe" / "protected_I_so5_so4_candidate.json"
DEFAULT_DISPOSITION = ROOT / "physics" / "ftoe" / "protected_I_candidate_disposition_v04.json"


def evaluate(candidate: dict, disposition: dict) -> dict:
    gates = candidate.get("mandatory_admission_gates", {})
    failed = {name: status for name, status in gates.items() if str(status).startswith("FAIL")}
    expected = disposition.get("mandatory_failed_gate")
    consistent = bool(failed) and expected in failed
    return {
        "schema": "FTOE-PROTECTED-I-DISPOSITION-GATE-v0.4",
        "failed_mandatory_gates": failed,
        "declared_failed_gate": expected,
        "candidate_fail_required": bool(failed),
        "disposition_consistent": consistent,
        "gate": "FAIL_CURRENT_MINIMAL_CANDIDATE" if consistent else "INCONSISTENT_DISPOSITION",
        "downstream_candidate_work": "STOP_AND_VERSION_SUCCESSOR" if consistent else "BLOCKED_RECONCILE",
        "scope_limit": disposition.get("scope_limit"),
        "no_retuning": bool(disposition.get("no_retuning")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--disposition", type=Path, default=DEFAULT_DISPOSITION)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    disposition = json.loads(args.disposition.read_text(encoding="utf-8"))
    result = evaluate(candidate, disposition)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    if result["gate"] != "FAIL_CURRENT_MINIMAL_CANDIDATE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
