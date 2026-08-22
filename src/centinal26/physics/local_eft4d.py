"""Restricted 4D local-EFT domain plugin for the theory kernel.

Initial scope: real scalar extensions around a GR+SM baseline. The plugin is a
benchmark domain, not the definition of all fundamental theories.
"""
from __future__ import annotations

from dataclasses import dataclass

from .theory_kernel import CandidateRecord, PropositionEvidence, TestStatus, TheoryCore


@dataclass(frozen=True)
class ScalarOperator:
    name: str
    mass_dimension: int
    coefficient_dimension: int
    real: bool = True
    gauge_invariant: bool = True

    @property
    def total_dimension(self) -> int:
        return self.mass_dimension + self.coefficient_dimension


def make_scalar_candidate(*, operators: list[ScalarOperator], z2: bool = False, cutoff: str = "Lambda") -> CandidateRecord:
    theory = TheoryCore(
        hypothesis_space="LocalEFT4D/scalar-v1",
        fundamental_objects=("metric", "SM_fields", "real_scalar_chi"),
        declared_symmetries=("diffeomorphism", "Lorentz", "SM_gauge") + (("Z2_chi",) if z2 else ()),
        dynamics_kind="local_action",
        assumptions=("4D", "local_EFT", "natural_units"),
        regime_of_validity=f"E << {cutoff}",
        unification_claim="COUPLED_SECTORS_ONLY",
    )
    payload = {
        "cutoff": cutoff,
        "z2": z2,
        "operators": [o.__dict__ for o in operators],
    }
    return CandidateRecord(
        theory=theory,
        domain_payload=payload,
        obligations=["well_formed", "dimensions_consistent", "reality_consistent"],
        provenance={"domain_plugin": "LocalEFT4D/scalar-v1"},
    )


def evaluate_basic_consistency(candidate: CandidateRecord) -> list[PropositionEvidence]:
    ops = [ScalarOperator(**x) for x in candidate.domain_payload.get("operators", [])]
    evidence: list[PropositionEvidence] = []
    evidence.append(
        PropositionEvidence(
            proposition="well_formed",
            scope="LocalEFT4D/scalar-v1 payload",
            assumptions=("operator metadata is complete",),
            method="schema-level domain checks",
            status=TestStatus.PASS if ops else TestStatus.FAIL,
            evidence_type="symbolic_structure",
            validator_id="local_eft4d.basic",
            validator_version="1.0",
            details={"operator_count": len(ops)},
        )
    )
    bad_dim = [o.name for o in ops if o.total_dimension != 4]
    evidence.append(
        PropositionEvidence(
            proposition="dimensions_consistent",
            scope="declared 4D Lagrangian terms only",
            assumptions=("hbar=c=1", "Lagrangian density has mass dimension 4"),
            method="operator_dimension + coefficient_dimension == 4",
            status=TestStatus.PASS if not bad_dim else TestStatus.FAIL,
            evidence_type="analytic_check",
            validator_id="local_eft4d.dimensions",
            validator_version="1.0",
            details={"failing_operators": bad_dim},
        )
    )
    nonreal = [o.name for o in ops if not o.real]
    evidence.append(
        PropositionEvidence(
            proposition="reality_consistent",
            scope="declared operator metadata only",
            assumptions=("real=True denotes a Hermitian/reality-qualified operator in this restricted plugin",),
            method="metadata gate",
            status=TestStatus.PASS if not nonreal else TestStatus.FAIL,
            evidence_type="symbolic_check",
            validator_id="local_eft4d.reality",
            validator_version="1.0",
            details={"failing_operators": nonreal},
        )
    )
    candidate.evidence.extend(evidence)
    return evidence
