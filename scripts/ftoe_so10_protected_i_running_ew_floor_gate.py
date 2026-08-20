"""Fail-closed RG-improved electroweak gauge-floor gate for protected-I successors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.ftoe_so10_running_ew_gauge_floor_gate import calculate
except ModuleNotFoundError:  # direct `python scripts/...` execution
    from ftoe_so10_running_ew_gauge_floor_gate import calculate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "physics" / "ftoe" / "protected_I_running_ew_floor_v06.json"


def evaluate(contract: dict) -> dict:
    result = calculate(mu_i=float(contract["mu_I_GeV"]))
    reference = float(contract["reference_lower_scale_bound_GeV"])
    tighter = result.cutoff_max_GeV < reference
    above_target = result.cutoff_max_GeV > float(contract["mu_I_GeV"])
    consistent = tighter and above_target and result.scientific_gate_status == "FAIL"
    return {
        "schema": "FTOE-PROTECTED-I-RUNNING-EW-FLOOR-GATE-v0.6",
        "gate": "DERIVED_RUNNING_EW_FLOOR" if consistent else "INCONSISTENT_RUNNING_EW_FLOOR",
        "cutoff_max_GeV": result.cutoff_max_GeV,
        "cutoff_max_TeV": result.cutoff_max_TeV,
        "reference_lower_scale_bound_GeV": reference,
        "tightening_fraction": 1.0 - result.cutoff_max_GeV / reference,
        "tightening_percent": 100.0 * (1.0 - result.cutoff_max_GeV / reference),
        "target_to_cutoff_ratio": result.cutoff_max_GeV / float(contract["mu_I_GeV"]),
        "C_gauge_at_cutoff": result.C_gauge_at_cutoff,
        "g2_at_cutoff": result.g2_at_cutoff,
        "gY_at_cutoff": result.gY_at_cutoff,
        "rg_shift_percent_vs_fixed_mz": result.rg_shift_percent,
        "scientific_status": "REVIEW",
        "admission_rule": contract["admission_rule"],
        "scope_limit": contract["scope_limit"],
        "primary_sources": contract["primary_sources"],
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
    if output["gate"] != "DERIVED_RUNNING_EW_FLOOR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
