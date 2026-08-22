from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "continuum_limit_contract.json"


def evaluate() -> dict[str, object]:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    req = data["audited_requirements"]
    facts = data["source_derived_facts"]
    checks = {
        "finite_parent_preserved": data["dependency"] == "PASS_BOUNDED_MULTI_MODE_REGULATOR_STRESS",
        "finite_to_typeIII_possibility_preserved": facts["finite_type_I_truncations_can_participate_in_a_type_III_infinite_product_limit"] is True,
        "no_false_typeIII_no_go": facts["type_III_is_ruled_out_by_finite_type_I_truncations_alone"] is False,
        "current_limit_not_claimed": facts["current_finite_parent_defines_such_a_limit"] is False,
        "missing_embedding_maps_recorded": req["explicit_inclusion_maps_A_m_to_A_mplus1"] is False,
        "missing_infinite_state_sequence_recorded": req["infinite_mode_frequency_or_state_sequence"] is False,
        "missing_state_compatibility_recorded": req["compatible_state_family_under_embeddings"] is False,
        "missing_topology_recorded": req["declared_operator_topology_or_GNS_limit"] is False,
        "missing_modular_domain_recorded": req["continuum_modular_generator_domain"] is False,
        "missing_type_invariant_recorded": req["type_discriminating_invariant_target"] is False,
        "fail_closed_verdict": data["verdict"] == "UNRESOLVED_MISSING_INDUCTIVE_OR_INFINITE_PRODUCT_LIMIT_DATA",
    }
    return {
        "execution_pass": all(checks.values()),
        "scientific_pass": False,
        "checks": checks,
        "verdict": data["verdict"],
        "smallest_missing_inputs": data["smallest_missing_inputs"],
    }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
