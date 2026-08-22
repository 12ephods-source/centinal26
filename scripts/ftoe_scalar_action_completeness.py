from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = (
    ROOT / "physics/ftoe/FTOE_COMPLETE_SCALAR_ACTION_COVERAGE_2026-08-22.json"
)
EXPECTED_FIELDS = {"210_H", "45_H", "126_H", "10_C,H", "protected-I"}
EXPECTED_MISSING = {
    "210-self-sector",
    "210-45-mixed-sector",
    "210-126-mixed-sector",
    "210-10C-mixed-sector",
    "protected-I-self-sector",
    "210-protected-I-mixed-sector",
    "45-protected-I-mixed-sector",
    "126-protected-I-mixed-sector",
    "10C-protected-I-mixed-sector",
    "multi-representation-renormalizable-invariant-basis",
}


def evaluate(path: Path = DEFAULT_INVENTORY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_rows = data.get("source_basis", [])
    missing_rows = data.get("required_missing_coverage", [])
    missing_by_id = {
        row.get("id"): row
        for row in missing_rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }

    source_paths_exist = all(
        isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and (ROOT / row["path"]).is_file()
        for row in source_rows
    )
    all_missing_fail_closed = all(
        missing_by_id.get(item_id, {}).get("status") == "MISSING_SOURCE"
        for item_id in EXPECTED_MISSING
    )

    checks = {
        "schema": data.get("schema")
        == "frost.ftoe.complete_scalar_action_coverage/v1",
        "field_set_exact": set(data.get("field_set", [])) == EXPECTED_FIELDS,
        "source_paths_exist": source_paths_exist,
        "required_missing_ids_present": EXPECTED_MISSING.issubset(missing_by_id),
        "missing_sectors_fail_closed": all_missing_fail_closed,
        "pairwise_not_complete": data.get("pairwise_coverage_is_complete") is False,
        "pairwise_not_sufficient": data.get(
            "pairwise_coverage_is_sufficient_for_action_completeness"
        )
        is False,
        "invariant_basis_not_complete": data.get(
            "renormalizable_invariant_basis_complete"
        )
        is False,
        "action_not_frozen": data.get("complete_action_frozen") is False,
        "no_invented_couplings": data.get("invented_coupling_values") == [],
        "scientific_status_fail_closed": data.get("scientific_status")
        == "BLOCKED_MISSING_SOURCE",
        "execution_state_missing_source": data.get("execution_state")
        == "MISSING_SOURCE",
        "verdict_is_bounded": data.get("canonical_verdict")
        == "BLOCKED_COMPLETE_SCALAR_ACTION_NOT_ENUMERATED",
        "next_transition_requires_invariant_basis": "invariant basis"
        in str(data.get("next_legitimate_transition", "")).lower(),
    }
    execution_pass = all(checks.values())
    return {
        "schema": "frost.ftoe.scalar_action_completeness_check/v1",
        "execution_pass": execution_pass,
        "scientific_pass": False,
        "canonical_verdict": data.get("canonical_verdict"),
        "checks": checks,
        "missing_coverage_ids": sorted(missing_by_id),
        "next_legitimate_transition": data.get("next_legitimate_transition"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inventory = args.inventory
    if not inventory.is_absolute():
        inventory = ROOT / inventory
    result = evaluate(inventory)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
