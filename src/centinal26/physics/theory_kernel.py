"""Small generic kernel for evidence-governed fundamental-theory search.

The kernel is intentionally domain-neutral. Domain plugins define mathematical
content; validators establish scoped propositions. Nothing here can promote a
candidate to empirical or scientific truth.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CandidateStatus(str, Enum):
    GENERATED = "GENERATED"
    WELL_FORMED = "WELL_FORMED"
    CONSISTENCY_SURVIVOR = "CONSISTENCY_SURVIVOR"
    DERIVATION_SURVIVOR = "DERIVATION_SURVIVOR"
    NUMERICAL_SURVIVOR = "NUMERICAL_SURVIVOR"
    PREDICTION_REGISTERED = "PREDICTION_REGISTERED"
    EMPIRICALLY_COMPARED = "EMPIRICALLY_COMPARED"
    SURVIVES_CURRENT_EVIDENCE = "SURVIVES_CURRENT_EVIDENCE"
    REJECTED = "REJECTED"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"
    EQUIVALENT = "EQUIVALENT"
    OBSERVATIONALLY_INDISTINGUISHABLE = "OBSERVATIONALLY_INDISTINGUISHABLE"
    SUPERSEDED = "SUPERSEDED"


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TheoryCore:
    hypothesis_space: str
    fundamental_objects: tuple[str, ...]
    declared_symmetries: tuple[str, ...]
    dynamics_kind: str
    parameters: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    regime_of_validity: str = "UNSPECIFIED"
    unification_claim: str = "UNSPECIFIED"

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_space": self.hypothesis_space,
            "fundamental_objects": sorted(self.fundamental_objects),
            "declared_symmetries": sorted(self.declared_symmetries),
            "dynamics_kind": self.dynamics_kind,
            "parameters": sorted(self.parameters),
            "assumptions": sorted(self.assumptions),
            "regime_of_validity": self.regime_of_validity,
            "unification_claim": self.unification_claim,
        }

    @property
    def theory_id(self) -> str:
        raw = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return "TH-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


@dataclass(frozen=True)
class PropositionEvidence:
    proposition: str
    scope: str
    assumptions: tuple[str, ...]
    method: str
    status: TestStatus
    evidence_type: str
    validator_id: str
    validator_version: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateRecord:
    theory: TheoryCore
    domain_payload: dict[str, Any]
    status: CandidateStatus = CandidateStatus.GENERATED
    parents: list[str] = field(default_factory=list)
    transformation: str | None = None
    obligations: list[str] = field(default_factory=list)
    evidence: list[PropositionEvidence] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def candidate_id(self) -> str:
        payload = {
            "theory": self.theory.canonical_dict(),
            "domain_payload": self.domain_payload,
            "parents": sorted(self.parents),
            "transformation": self.transformation,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "CTH-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    def evidence_debt(self, weights: dict[str, float] | None = None) -> float:
        weights = weights or {}
        passed = {
            e.proposition
            for e in self.evidence
            if e.status is TestStatus.PASS
        }
        return sum(weights.get(o, 1.0) for o in self.obligations if o not in passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "theory_id": self.theory.theory_id,
            "status": self.status.value,
            "theory": self.theory.canonical_dict(),
            "domain_payload": self.domain_payload,
            "parents": self.parents,
            "transformation": self.transformation,
            "obligations": self.obligations,
            "evidence": [asdict(e) for e in self.evidence],
            "provenance": self.provenance,
        }


def promotion_allowed(current: CandidateStatus, target: CandidateStatus, evidence: list[PropositionEvidence]) -> bool:
    """Fail closed on unsupported promotion.

    This is intentionally conservative. It encodes only the first software/theory
    boundary and leaves empirical/scientific promotion to separate governance.
    """
    if target is CandidateStatus.WELL_FORMED:
        return any(e.proposition == "well_formed" and e.status is TestStatus.PASS for e in evidence)
    if target is CandidateStatus.CONSISTENCY_SURVIVOR:
        required = {"dimensions_consistent", "reality_consistent"}
        passed = {e.proposition for e in evidence if e.status is TestStatus.PASS}
        return required <= passed
    if target in {
        CandidateStatus.EMPIRICALLY_COMPARED,
        CandidateStatus.SURVIVES_CURRENT_EVIDENCE,
    }:
        return False
    return current == target
