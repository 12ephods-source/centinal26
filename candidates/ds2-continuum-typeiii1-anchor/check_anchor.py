from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANCHOR = HERE / "continuum_typeiii1_anchor.json"


def evaluate() -> dict[str, object]:
    data = json.loads(ANCHOR.read_text(encoding="utf-8"))
    claims = {item["id"]: item for item in data["primary_source_claims"]}
    unresolved = data["unresolved_bridge"]
    checks = {
        "scope_is_ds2_free_field": data["scope"] == "two-dimensional de Sitter canonical free scalar local observable net",
        "finite_parent_is_scoped": data["finite_dependency"]["scope_boundary"] == "finite Type-I geometry-bearing surrogate only",
        "continuum_control_is_scoped": "not physical de Sitter" in data["control_dependency"]["scope_boundary"],
        "typeiii1_claim_is_primary_source_bound": claims["DS2_FREE_LOCAL_TYPE_III1"]["verified_from_source_text"] is True,
        "typeiii1_location_is_specific": claims["DS2_FREE_LOCAL_TYPE_III1"]["direct_text_location"] == "Chapter 8, Proposition 8.2.3(iii)",
        "kms_claim_is_source_bound": claims["DS_GEODESIC_KMS"]["verified_from_source_text"] is True,
        "target_is_typeiii1": data["established_target"]["local_factor_type"] == "HYPERFINITE_TYPE_III_1",
        "bridge_remains_unresolved": len(unresolved) >= 4,
        "finite_to_continuum_promotion_forbidden": any("finite Type-I regulator itself" in item for item in data["forbidden_inferences"]),
        "verdict_is_source_anchor_only": data["verdict"] == "PASS_DS2_CONTINUUM_TYPE_III1_SOURCE_ANCHOR",
        "next_gate_is_two_axis_bridge": data["next_gate"] == "TWO_AXIS_WEYL_BRIDGE_LOCAL_DIMENSION_THEN_MODE_LIMIT",
    }
    return {
        "execution_pass": all(checks.values()),
        "scientific_pass": False,
        "verdict": data["verdict"],
        "checks": checks,
        "continuum_target": data["established_target"],
        "unresolved_bridge": unresolved,
        "next_gate": data["next_gate"],
    }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
