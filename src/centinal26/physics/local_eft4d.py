"""Restricted scalar EFT benchmark domain for the theory-testing kernel."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from .theory_kernel import CandidateRecord, ProofObligation, TheoryCore


class MetricConvention(str, Enum):
    MOSTLY_PLUS = "-+++"
    MOSTLY_MINUS = "+---"


@dataclass(frozen=True)
class Parameter:
    name: str
    mass_dimension: int
    positive: bool | None = None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScalarTerm:
    name: str
    chi_power: int
    derivatives: int
    coefficient: Parameter
    coefficient_sign: int
    curvature_power: int = 0

    @property
    def operator_dimension(self) -> int:
        # In 4D a canonically normalized real scalar has mass dimension 1;
        # each derivative has dimension 1 and R has dimension 2.
        return self.chi_power + self.derivatives + 2 * self.curvature_power

    @property
    def term_dimension(self) -> int:
        return self.operator_dimension + self.coefficient.mass_dimension

    @property
    def z2_even(self) -> bool:
        return self.chi_power % 2 == 0

    def canonical_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "chi_power": self.chi_power,
            "derivatives": self.derivatives,
            "coefficient": self.coefficient.canonical_dict(),
            "coefficient_sign": self.coefficient_sign,
            "curvature_power": self.curvature_power,
        }


@dataclass(frozen=True)
class LocalScalarEFT4D:
    terms: tuple[ScalarTerm, ...]
    z2: bool = False
    cutoff: Parameter = Parameter("Lambda", 1, True)
    metric: MetricConvention = MetricConvention.MOSTLY_PLUS

    def canonical_dict(self) -> dict[str, object]:
        terms = sorted((t.canonical_dict() for t in self.terms), key=lambda x: str(x))
        return {
            "domain": "LocalScalarEFT4D/v2",
            "terms": terms,
            "z2": self.z2,
            "cutoff": self.cutoff.canonical_dict(),
            "metric": self.metric.value,
        }

    @property
    def input_hash(self) -> str:
        import hashlib
        import json

        raw = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def make_scalar_candidate(model: LocalScalarEFT4D) -> CandidateRecord:
    theory = TheoryCore(
        hypothesis_space="LocalScalarEFT4D/v2",
        fundamental_objects=("real_scalar_chi",),
        declared_symmetries=(("Z2_chi",) if model.z2 else ()),
        dynamics_kind="local_scalar_effective_action_overlay",
        assumptions=("4D", "local_EFT", "natural_units", f"metric={model.metric.value}"),
        regime_of_validity=f"E << {model.cutoff.name}",
        unification_claim="COUPLED_SECTORS_ONLY",
    )
    scope = "LocalScalarEFT4D/v2 declared action"
    obligations = [
        ProofObligation("well_formed", scope, ("structural_check",)),
        ProofObligation("dimensions_consistent", scope, ("derived_structural_check",)),
        ProofObligation("declared_symmetries_respected", scope, ("derived_symmetry_check",)),
        ProofObligation("kinetic_sign_consistent", scope, ("derived_dynamical_check",)),
    ]
    return CandidateRecord(
        theory=theory,
        domain_model=model,
        obligations=obligations,
        provenance={"domain_plugin": "LocalScalarEFT4D/v2"},
    )
