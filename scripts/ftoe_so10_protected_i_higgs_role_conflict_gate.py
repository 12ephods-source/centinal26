"""Fail-closed adjudication of direct protected-I identification in Littlest Higgs.

Execution PASS and scientific PASS are intentionally distinct. This program exits
successfully when it can deterministically reproduce the frozen scientific verdict,
including an expected FAIL verdict.
"""

import argparse
import json
import pathlib


EXPECTED_FAIL = "FAIL_DIRECT_IDENTIFICATION_HIGGS_ROLE_CONFLICT"


def adjudicate(contract: dict) -> dict:
    ftoe = contract["frozen_ftoe_facts"]
    ref = contract["frozen_reference_facts"]

    checks = {
        "ftoe_I_is_distinct": bool(ftoe["protected_I_is_distinct_informational_doublet"]),
        "ftoe_I_has_independent_mass_parameter": float(ftoe["protected_I_has_independent_mu_I_GeV"]) > 0,
        "ftoe_I_has_separate_threshold": float(ftoe["protected_I_threshold_GeV"]) > 0,
        "ftoe_action_lists_I_separately": bool(
            ftoe["complete_action_lists_protected_I_separately_from_Higgs_sector"]
        ),
        "reference_has_single_light_pNGB_doublet": bool(
            ref["single_light_pNGB_electroweak_doublet"]
        ),
        "reference_pNGB_is_SM_Higgs": ref["pNGB_doublet_role"] == "Standard Model Higgs",
        "reference_low_energy_is_minimal_SM": ref["below_TeV_effective_theory"] == "minimal Standard Model",
    }

    conflict = all(checks.values())
    verdict = EXPECTED_FAIL if conflict else "REVIEW_IDENTITY_CONFLICT_NOT_ESTABLISHED"

    return {
        "schema": "FTOE-PROTECTED-I-HIGGS-ROLE-ADJUDICATION-v0.8",
        "checks": checks,
        "scientific_verdict": verdict,
        "execution_status": "PASS",
        "scope_limit": contract["scope_limit"],
        "no_retuning": bool(contract["no_retuning"]),
        "derived_statement": (
            "The single light pNGB doublet of the frozen Littlest-Higgs reference is the SM Higgs. "
            "FToE requires protected I as a distinct informational doublet with its own mass parameter "
            "and threshold. Direct identification therefore collapses two distinct roles and fails the "
            "frozen identity gate."
            if conflict
            else "The frozen inputs are insufficient to establish the direct-identification conflict."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--json", type=pathlib.Path)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    result = adjudicate(contract)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")

    if result["scientific_verdict"] != contract["expected_verdict"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
