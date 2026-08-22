from __future__ import annotations

import json
from pathlib import Path

CONTRACT = Path("physics/ftoe/protected_I_so6_second_doublet_ew_embedding_v15.json")


def evaluate() -> dict:
    data = json.loads(CONTRACT.read_text())
    derivation = data["derivation"]
    gates = data["mandatory_gates"]
    checks = {
        "parent_frozen": data["parent_head"] == "0dbefff119005505ed733190ed29a19a70079dd2",
        "source_frozen": data["primary_source"] == "arXiv:1105.5403",
        "so4_decomposition": derivation["each_SO4_4"] == "(2,2) under SU(2)_L x SU(2)_R",
        "hypercharge_rule": derivation["hypercharge_rule"] == "Y=T_R^3+X with X=0 for the scalar candidate",
        "positive_hypercharge_doublet": derivation["second_doublet_positive_hypercharge_component"] == "SU(2)_L doublet, Y=+1/2",
        "matches_frozen_I": derivation["matches_frozen_low_energy_I_gauge_quantum_numbers"] is True,
        "downstream_fail_closed": all(
            gates[key] == "NOT_DERIVED"
            for key in (
                "mu_I_13p5_TeV_mass_matching",
                "SO10_embedding_or_sequestering",
                "portal_suppression",
                "representation_specific_radiative_mass",
                "precision_and_partner_constraints",
            )
        ),
        "no_retuning": data["no_retuning"] is True,
        "still_review": data["scientific_status"] == "REVIEW",
    }
    return {
        "scientific_transition": data["scientific_transition"],
        "checks": checks,
        "pass": all(checks.values()),
        "scientific_status": data["scientific_status"],
    }


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)
