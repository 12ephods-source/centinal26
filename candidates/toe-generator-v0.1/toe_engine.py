from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "registry.json"


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def index_components(registry: dict) -> dict:
    return {
        sector: {component["id"]: component for component in components}
        for sector, components in registry["components"].items()
    }


def candidate_id(genome: dict[str, str]) -> str:
    return "TOE-" + canonical_hash(genome)[:16].upper()


def test_candidate(genome: dict[str, str], registry: dict | None = None) -> dict:
    registry = registry or load_registry()
    index = index_components(registry)
    components = {
        sector: index[sector][component_id]
        for sector, component_id in genome.items()
    }

    gates: dict[str, str] = {}
    reasons: list[str] = []

    gates["G0_PROVENANCE"] = "PASS"

    hard_failures = [
        component["id"]
        for component in components.values()
        if component.get("hard_fail")
    ]
    gates["G1_NO_FALSIFIED_COMPONENT"] = "FAIL" if hard_failures else "PASS"
    if hard_failures:
        reasons.append("Contains falsified component(s): " + ", ".join(hard_failures))

    core = components["core"]
    gates["G2_CORE_CLOSURE"] = "REVIEW" if core.get("issues") else "PASS"
    if core.get("issues"):
        reasons.append(
            "The displayed core action is not mathematically/parametrically closed."
        )

    noncore = [
        component for sector, component in components.items() if sector != "core"
    ]
    derived_count = sum(bool(component.get("derived")) for component in noncore)
    derivation_coverage = derived_count / len(noncore)
    if derivation_coverage >= 0.8:
        gates["G3_DERIVATION_COVERAGE"] = "PASS"
    elif derivation_coverage >= 0.4:
        gates["G3_DERIVATION_COVERAGE"] = "REVIEW"
    else:
        gates["G3_DERIVATION_COVERAGE"] = "NOT_TESTED"
    if derivation_coverage < 0.8:
        reasons.append(
            f"Only {derived_count}/{len(noncore)} selected sectors are marked "
            "derived from the displayed core."
        )

    inflation = components["inflation"]
    if inflation["id"] == "FTOE-INFL-P3-BEST":
        gates["G4_INFLATION"] = "FAIL"
        reasons.append(
            "Historical Phase-3 point retains r≈0.09081 and failed normalization."
        )
    elif inflation["id"] == "FUEF-INFL-GATE2B-EXACT":
        r_value = inflation["observables"]["r"]
        if r_value >= 0.036:
            gates["G4_INFLATION"] = "FAIL"
            reasons.append("Exact Gate-2B r fails the stored tensor bound r<0.036.")
        else:
            gates["G4_INFLATION"] = "REVIEW"
            reasons.append(
                "Gate-2B exact/numerical checks pass and r<0.036, but "
                "self-reheating is a conditional kill and external CMB likelihood "
                "is not executed."
            )
    else:
        gates["G4_INFLATION"] = "NOT_TESTED"

    dark = components["dark"]
    if dark.get("hard_fail"):
        gates["G5_DARK"] = "FAIL"
    elif dark["status"] == "UNRESOLVED":
        gates["G5_DARK"] = "NOT_TESTED"
    else:
        gates["G5_DARK"] = "REVIEW"
        if dark["id"] == "DARK-LCDM-EMPIRICAL-LIMIT":
            reasons.append(
                "ΛCDM dark matter is an empirical low-energy envelope, not a ToE "
                "microphysical derivation."
            )

    neutrino = components["neutrino"]
    if neutrino["id"] == "NU-MSW-LMA-LIMIT":
        gates["G6_NEUTRINO"] = "REVIEW"
        reasons.append(
            "MSW-LMA is an empirical interface, not a derivation from this candidate core."
        )
    elif neutrino["id"] == "NU-THETA23-47-TOY":
        gates["G6_NEUTRINO"] = "NOT_TESTED"
        reasons.append(
            "The θ23=47° executable is a toy sensitivity/kill-condition interface, "
            "not empirical validation."
        )
    else:
        gates["G6_NEUTRINO"] = "NOT_TESTED"

    unification = components["unification"]
    information = components["information"]
    if (
        unification["status"] == "ACTIVE_HYPOTHESIS"
        and information["status"] == "ACTIVE_HYPOTHESIS"
    ):
        gates["G7_UV_CLOSURE"] = "REVIEW"
        reasons.append(
            "GUT/information chain remains incomplete; μ_I is constrained by the β "
            "target rather than independently derived."
        )
    else:
        gates["G7_UV_CLOSURE"] = "NOT_TESTED"

    cosmology = components["cosmology"]
    if cosmology.get("hard_fail"):
        gates["G8_COSMOLOGY"] = "FAIL"
        reasons.append(
            "The positive-R² bounce assertion as written is retained only as a failed "
            "regression case."
        )
    else:
        gates["G8_COSMOLOGY"] = "REVIEW"
        reasons.append(
            "GR+ΛCDM is used as an empirical IR limit; it does not supply a generated "
            "UV origin cosmology."
        )

    gates["G9_EXTERNAL_CERTIFICATION"] = "PENDING_INDEPENDENT_CROSS_CHECK"

    values = set(gates.values())
    if "FAIL" in values:
        verdict = "FAIL"
    elif all(
        value == "PASS"
        for gate, value in gates.items()
        if gate != "G9_EXTERNAL_CERTIFICATION"
    ):
        verdict = "VIABLE_FOR_NEXT_GATE"
    else:
        verdict = "REVIEW"

    base_score = sum(component.get("score", 0) for component in components.values())
    score = (
        base_score
        + 5 * sum(value == "PASS" for value in gates.values())
        - 100 * len(hard_failures)
        - 4 * sum(value == "NOT_TESTED" for value in gates.values())
        - 2 * sum(value == "REVIEW" for value in gates.values())
        + round(10 * derivation_coverage, 3)
    )

    return {
        "candidate_id": candidate_id(genome),
        "genome": genome,
        "component_status": {
            sector: component["status"] for sector, component in components.items()
        },
        "gates": gates,
        "derivation_coverage": derivation_coverage,
        "score": score,
        "verdict": verdict,
        "certification_permitted": False,
        "reasons": reasons,
    }


def enumerate_candidates(include_falsified: bool = False) -> list[dict]:
    registry = load_registry()
    sectors = list(registry["components"])
    pools: list[list[str]] = []
    for sector in sectors:
        components = registry["components"][sector]
        if not include_falsified:
            components = [
                component for component in components if not component.get("hard_fail")
            ]
        pools.append([component["id"] for component in components])

    results = []
    for choices in itertools.product(*pools):
        genome = dict(zip(sectors, choices, strict=True))
        results.append(test_candidate(genome, registry))
    results.sort(
        key=lambda result: (result["verdict"] != "FAIL", result["score"]),
        reverse=True,
    )
    return results


def regression_cases() -> dict[str, dict]:
    registry = load_registry()
    base = {
        "core": "FTOE-REC-v3",
        "inflation": "FUEF-INFL-GATE2B-EXACT",
        "dark": "FTOE-DARK-NONMIN-v0",
        "neutrino": "NU-MSW-LMA-LIMIT",
        "unification": "FTOE-GUT-v3",
        "information": "FTOE-INFO-BETA-v3",
        "cosmology": "GR-LCDM-NULL-LIMIT",
    }
    cases = {"best_current_composite": test_candidate(base, registry)}

    phase3 = dict(base)
    phase3["inflation"] = "FTOE-INFL-P3-BEST"
    cases["historical_phase3_failure"] = test_candidate(phase3, registry)

    dark = dict(base)
    dark["dark"] = "FTOE-DARK-MIN-102"
    cases["historical_dark_failure"] = test_candidate(dark, registry)

    bounce = dict(base)
    bounce["cosmology"] = "FTOE-R2-BOUNCE-AS-WRITTEN"
    cases["historical_bounce_failure"] = test_candidate(bounce, registry)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evidence-gated candidate ToE generator/tester"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--top", type=int, default=10)
    generate.add_argument("--include-falsified", action="store_true")

    test = subparsers.add_parser("test")
    test.add_argument("--genome", type=Path)

    subparsers.add_parser("regressions")
    args = parser.parse_args()

    if args.command == "generate":
        candidates = enumerate_candidates(args.include_falsified)
        payload = {
            "schema": "frost-candidate-toe-generation/0.1",
            "candidate_count": len(candidates),
            "top": candidates[: args.top],
            "global_note": "No generated candidate may be called VERIFIED by this engine.",
        }
    elif args.command == "test":
        if args.genome:
            genome = json.loads(args.genome.read_text(encoding="utf-8"))
        else:
            genome = regression_cases()["best_current_composite"]["genome"]
        payload = test_candidate(genome)
    else:
        payload = regression_cases()

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
