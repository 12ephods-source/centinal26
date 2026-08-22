"""Candidate Theory-of-Everything generator.

Reconstructed successor to the historical QuantityTheoryGeneratorAgent lineage.
Generated theories are PROPOSED hypotheses. This module cannot promote, validate,
or canonize its own output.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
from dataclasses import asdict, dataclass
from typing import Any

VERSION = "1.0.0-reconstructed"

GRAVITY = (
    ("GR_EFT", "General covariance with low-energy EFT gravity", "M_P^2 R/2 - Lambda + EFT corrections"),
    ("R2_GRAVITY", "General covariance with an R^2 correction", "M_P^2 R/2 + alpha_R R^2 - Lambda"),
    ("SCALAR_TENSOR", "Generally covariant scalar-tensor extension", "F(phi)R/2 - Z(phi)(d phi)^2/2 - V(phi)"),
)
VISIBLE = (
    ("SM_BASELINE", "Standard Model accessible-sector baseline", "L_SM"),
    ("SM_PLUS_NU", "Standard Model plus a neutrino-mass sector", "L_SM + L_nu"),
)
HIDDEN = (
    ("NONE", "No new accessible hidden-sector field", "0"),
    ("Z2_SCALAR", "Real Z2-odd scalar sector", "-(d chi)^2/2 - m_chi^2 chi^2/2 - lambda_chi chi^4/4"),
    ("DARK_U1", "Hidden U(1)_D gauge sector", "-F_D^2/4 - m_D^2 A_D^2/2"),
)
BRIDGES = (
    ("GRAVITY_ONLY", "Universal gravitational coupling only", "0", None),
    ("HIGGS_PORTAL", "Renormalizable Higgs portal", "-lambda_Hchi |H|^2 chi^2/2", "Z2_SCALAR"),
    ("KINETIC_MIXING", "Abelian kinetic mixing", "-(epsilon/2) B_mn F_D^mn", "DARK_U1"),
)
QUANTUM = (
    ("EFT_QUANTUM", "Controlled low-energy quantum EFT; no UV completion claimed"),
    ("EMERGENT_MICRO", "Quantum probabilities treated as potentially emergent; requires a distinguishing observable"),
)


@dataclass(frozen=True)
class CandidateTheory:
    candidate_id: str
    status: str
    objective: str
    components: dict[str, str]
    principles: list[str]
    action_terms: list[str]
    assumptions: list[str]
    required_next_checks: list[str]
    falsifiers: list[str]
    prediction_domains: list[str]
    complexity_score: int
    novelty_score: int
    provenance: dict[str, Any]


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _valid(hidden: tuple[str, str, str], bridge: tuple[str, str, str, str | None]) -> bool:
    return bridge[3] is None or bridge[3] == hidden[0]


def _candidate(parts: tuple[Any, ...], objective: str) -> CandidateTheory:
    gravity, visible, hidden, bridge, quantum = parts
    components = {
        "gravity": gravity[0],
        "visible": visible[0],
        "hidden": hidden[0],
        "bridge": bridge[0],
        "quantum_frame": quantum[0],
    }
    identity = {"objective": objective, "components": components}
    novelty = sum((gravity[0] != "GR_EFT", hidden[0] != "NONE", bridge[0] != "GRAVITY_ONLY", quantum[0] != "EFT_QUANTUM"))
    complexity = 1 + novelty + int(visible[0] != "SM_BASELINE")
    return CandidateTheory(
        candidate_id="TOE-" + _canonical_hash(identity)[:12].upper(),
        status="PROPOSED",
        objective=objective,
        components=components,
        principles=[gravity[1], visible[1], hidden[1], bridge[1], quantum[1]],
        action_terms=[gravity[2], visible[2], hidden[2], bridge[2]],
        assumptions=[
            "Recover tested General Relativity and Standard Model limits in their empirical domains.",
            "Locality, unitarity, and causality are required in the declared effective regime unless a controlled exception is stated.",
            "A generated mathematical structure is not empirical evidence.",
            "Synthetic self-consistency is not scientific validation.",
        ],
        required_next_checks=[
            "derive_field_equations",
            "check_dimensions_and_normalizations",
            "check_gr_and_sm_limits",
            "check_ghost_gradient_tachyon_stability",
            "check_gauge_and_anomaly_consistency",
            "run_independent_analytic_and_numerical_benchmarks",
            "confront_preregistered_predictions_with_external_data",
        ],
        falsifiers=[
            "failure_to_recover_established_low_energy_limits",
            "unavoidable_ghost_or_instability",
            "parameter_independent_prediction_excluded_by_external_data",
            "failure_of_preregistered_quantitative_prediction",
        ],
        prediction_domains=["cosmology", "gravitational_waves", "precision_gravity", "collider", "dark_sector", "neutrino_flavor"],
        complexity_score=complexity,
        novelty_score=novelty,
        provenance={
            "generator": f"candidate_toe_generator/{VERSION}",
            "reconstruction_basis": "QuantityTheoryGeneratorAgent",
            "identity_sha256": _canonical_hash(identity),
        },
    )


def generate_candidates(
    objective: str,
    *,
    count: int = 5,
    seed: int = 20260822,
    preference: str = "conservative",
) -> list[dict[str, Any]]:
    """Generate deterministic structured candidate research programs.

    preference: conservative | novel | simple | id
    """
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    if preference not in {"conservative", "novel", "simple", "id"}:
        raise ValueError("invalid preference")

    combos = [
        c
        for c in itertools.product(GRAVITY, VISIBLE, HIDDEN, BRIDGES, QUANTUM)
        if _valid(c[2], c[3])
    ]
    random.Random(seed).shuffle(combos)
    candidates = [_candidate(c, objective) for c in combos]

    if preference == "conservative":
        candidates.sort(key=lambda x: (x.novelty_score, x.complexity_score, x.candidate_id))
    elif preference == "novel":
        candidates.sort(key=lambda x: (-x.novelty_score, x.complexity_score, x.candidate_id))
    elif preference == "simple":
        candidates.sort(key=lambda x: (x.complexity_score, x.novelty_score, x.candidate_id))
    else:
        candidates.sort(key=lambda x: x.candidate_id)
    return [asdict(x) for x in candidates[:count]]


def self_test() -> dict[str, Any]:
    first = generate_candidates("unify gravity and quantum matter", count=8, seed=42)
    second = generate_candidates("unify gravity and quantum matter", count=8, seed=42)
    assert first == second
    assert len(first) == 8
    assert len({x["candidate_id"] for x in first}) == 8
    assert all(x["status"] == "PROPOSED" for x in first)
    assert all(x["required_next_checks"] and x["falsifiers"] for x in first)
    for item in generate_candidates("compatibility", count=50, preference="id"):
        c = item["components"]
        if c["bridge"] == "HIGGS_PORTAL":
            assert c["hidden"] == "Z2_SCALAR"
        if c["bridge"] == "KINETIC_MIXING":
            assert c["hidden"] == "DARK_U1"
    return {"status": "PASS", "version": VERSION, "checks": 7}
