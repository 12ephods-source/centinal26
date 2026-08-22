"""Scoped physics theory-testing engine for the first scalar-EFT domain."""
from __future__ import annotations

from collections.abc import Callable

from .local_eft4d import LocalScalarEFT4D, MetricConvention
from .theory_kernel import CandidateRecord, PropositionEvidence, TestStatus

Validator = Callable[[CandidateRecord], PropositionEvidence]
SCOPE = "LocalScalarEFT4D/v2 declared action"


def _evidence(
    candidate: CandidateRecord,
    *,
    proposition: str,
    method: str,
    status: TestStatus,
    evidence_type: str,
    validator_id: str,
    details: dict[str, object],
) -> PropositionEvidence:
    model = candidate.domain_model
    if not isinstance(model, LocalScalarEFT4D):
        raise TypeError("validator requires LocalScalarEFT4D")
    return PropositionEvidence(
        proposition=proposition,
        scope=SCOPE,
        assumptions=("4D", "natural units", f"metric={model.metric.value}"),
        method=method,
        status=status,
        evidence_type=evidence_type,
        validator_id=validator_id,
        validator_version="2.0",
        input_hash=model.input_hash,
        details=details,
    )


def validate_well_formed(candidate: CandidateRecord) -> PropositionEvidence:
    model = candidate.domain_model
    if not isinstance(model, LocalScalarEFT4D):
        raise TypeError("validator requires LocalScalarEFT4D")
    names = [t.name for t in model.terms]
    malformed = [
        t.name
        for t in model.terms
        if t.chi_power < 0 or t.derivatives < 0 or t.curvature_power < 0 or t.coefficient_sign not in {-1, 1}
    ]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    ok = bool(model.terms) and not malformed and not duplicate_names and model.cutoff.mass_dimension == 1
    return _evidence(
        candidate,
        proposition="well_formed",
        method="typed-domain schema and invariant checks",
        status=TestStatus.PASS if ok else TestStatus.FAIL,
        evidence_type="structural_check",
        validator_id="physics.local_scalar_eft.well_formed",
        details={"malformed_terms": malformed, "duplicate_names": duplicate_names},
    )


def validate_dimensions(candidate: CandidateRecord) -> PropositionEvidence:
    model = candidate.domain_model
    if not isinstance(model, LocalScalarEFT4D):
        raise TypeError("validator requires LocalScalarEFT4D")
    failing = [t.name for t in model.terms if t.term_dimension != 4]
    return _evidence(
        candidate,
        proposition="dimensions_consistent",
        method="derive operator dimension from scalar powers, derivatives and curvature; add coefficient dimension",
        status=TestStatus.PASS if not failing else TestStatus.FAIL,
        evidence_type="derived_structural_check",
        validator_id="physics.local_scalar_eft.dimensions",
        details={
            "failing_terms": failing,
            "term_dimensions": {t.name: t.term_dimension for t in model.terms},
        },
    )


def validate_declared_symmetries(candidate: CandidateRecord) -> PropositionEvidence:
    model = candidate.domain_model
    if not isinstance(model, LocalScalarEFT4D):
        raise TypeError("validator requires LocalScalarEFT4D")
    failing = [t.name for t in model.terms if model.z2 and not t.z2_even]
    return _evidence(
        candidate,
        proposition="declared_symmetries_respected",
        method="apply chi -> -chi parity to every represented scalar term",
        status=TestStatus.PASS if not failing else TestStatus.FAIL,
        evidence_type="derived_symmetry_check",
        validator_id="physics.local_scalar_eft.z2",
        details={"z2_declared": model.z2, "failing_terms": failing},
    )


def validate_kinetic_sign(candidate: CandidateRecord) -> PropositionEvidence:
    model = candidate.domain_model
    if not isinstance(model, LocalScalarEFT4D):
        raise TypeError("validator requires LocalScalarEFT4D")
    kinetic = [t for t in model.terms if t.chi_power == 2 and t.derivatives == 2 and t.curvature_power == 0]
    expected_sign = -1 if model.metric is MetricConvention.MOSTLY_PLUS else 1
    if len(kinetic) != 1:
        status = TestStatus.FAIL
        failing = [t.name for t in kinetic]
        reason = "expected exactly one canonical quadratic kinetic structure"
    else:
        status = TestStatus.PASS if kinetic[0].coefficient_sign == expected_sign else TestStatus.FAIL
        failing = [] if status is TestStatus.PASS else [kinetic[0].name]
        reason = "canonical kinetic sign under declared metric convention"
    return _evidence(
        candidate,
        proposition="kinetic_sign_consistent",
        method=reason,
        status=status,
        evidence_type="derived_dynamical_check",
        validator_id="physics.local_scalar_eft.kinetic",
        details={"expected_sign": expected_sign, "failing_terms": failing},
    )


class PhysicsTheoryTestingEngine:
    """Runs deterministic scoped validators and stores idempotent evidence."""

    def __init__(self, validators: tuple[Validator, ...] | None = None) -> None:
        self.validators = validators or (
            validate_well_formed,
            validate_dimensions,
            validate_declared_symmetries,
            validate_kinetic_sign,
        )

    def evaluate(self, candidate: CandidateRecord) -> list[PropositionEvidence]:
        results = [validator(candidate) for validator in self.validators]
        for result in results:
            candidate.add_evidence(result)
        return results
