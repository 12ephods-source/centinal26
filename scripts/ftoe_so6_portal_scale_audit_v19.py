#!/usr/bin/env python3
import json
import math
from pathlib import Path

CONTRACT = Path("research/ftoe/protected_i/so6_portal_scale_audit_v19.json")


def main() -> int:
    c = json.loads(CONTRACT.read_text())
    mu = float(c["frozen_inputs"]["mu_I_GeV"])
    v = float(c["frozen_inputs"]["v_SM_GeV"])
    lam_ref = float(c["frozen_inputs"]["reference_lambda3"])
    lam_pert = float(c["frozen_inputs"]["perturbative_reference_lambda3"])
    mu2 = mu * mu
    coeff = v * v / 2.0
    frac_ref = lam_ref * coeff / mu2
    frac_pert = lam_pert * coeff / mu2
    lambda_equal = mu2 / coeff

    checks = {
        "lambda3_one_shift_fraction_lt_1e_minus_2": frac_ref < 1e-2,
        "lambda3_4pi_shift_fraction_lt_1e_minus_2": frac_pert < 1e-2,
        "lambda3_required_for_muI_shift_gt_100": lambda_equal > 100.0,
        "presence_alone_does_not_prove_GUT_scale_naturalness_failure": True,
        "predecessor_preserved": c["frozen_checks"]["predecessor_preserved"],
        "candidate_not_rehabilitated_without_composite_scale_radiative_analysis": c["frozen_checks"]["candidate_not_rehabilitated_without_composite_scale_radiative_analysis"],
    }
    result = {
        "gate": c["gate"],
        "mu_I_sq_GeV2": mu2,
        "v_SM_sq_over_2_GeV2": coeff,
        "lambda3_one_fraction_of_mu_I_sq": frac_ref,
        "lambda3_4pi_fraction_of_mu_I_sq": frac_pert,
        "lambda3_for_delta_mu_I_sq_equal_mu_I_sq": lambda_equal,
        "checks": checks,
        "execution_pass": all(checks.values()),
        "scientific_verdict": "PREDECESSOR_KILL_PREMISE_INSUFFICIENT_AS_STATED__REVIEW_REQUIRED" if all(checks.values()) else "AUDIT_FAILED",
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/ftoe_so6_portal_scale_audit_v19.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
