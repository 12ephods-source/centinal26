"""Fail-closed lower-scale viability bound for future protected-I successors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.ftoe_so10_low_scale_protection_bound import calculate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "physics" / "ftoe" / "protected_I_lower_scale_bound_v05.json"


def evaluate(contract: dict) -> dict:
    result = calculate(
        mu_i=float(contract["mu_I_GeV"]),
        alpha=float(contract["alpha_reference"]),
        coefficient=float(contract["coefficient_C_reference"]),
    )
    consistent = (
        result.break_even_f_GeV > contract["mu_I_GeV"]
        and result.break_even_f_GeV < result.frozen_MU_GeV
        and result.lower_scale_branch_status == "REVIEW_REQUIRES_EXPLICIT_MECHANISM_AND_DERIVED_C"
    )
    return {
        "schema": "FTOE-PROTECTED-I-LOWER-SCALE-GATE-v0.5",
        "gate": "DERIVED_REFERENCE_BOUND" if consistent else "INCONSISTENT_BOUND",
        "break_even_f_GeV": result.break_even_f_GeV,
        "break_even_f_TeV": result.break_even_f_TeV,
        "max_C_at_frozen_MU": result.max_C_at_frozen_MU,
        "required_C_suppression_orders_at_frozen_MU": result.required_C_suppression_orders_at_frozen_MU,
        "successor_status": result.lower_scale_branch_status,
        "scientific_status": "REVIEW",
        "scope_limit": contract["scope_limit"],
        "no_retuning": bool(contract["no_retuning"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    output = evaluate(contract)
    text = json.dumps(output, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    if output["gate"] != "DERIVED_REFERENCE_BOUND":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
