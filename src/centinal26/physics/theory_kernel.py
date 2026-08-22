"""Evidence-governed kernel for bounded fundamental-theory search."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol


class CandidateStatus(str, Enum):
    GENERATED = "GENERATED"
    WELL_FORMED = "WELL_FORMED"
    STRUCTURALLY_CHECKED = "STRUCTURALLY_CHECKED"
    DYNAMICALLY_CHECKED = "DYNAMICALLY_CHECKED"
    PREDICTION_REGISTERED = "PREDICTION_REGISTERED"
    EMPIRICALLY_COMPARED = "EMPIRICALLY_COMPARED"
    SURVIVES_CURRENT_EVIDENCE = "SURVIVES_CURRENT_EVIDENCE"
    REJECTED = "REJECTED"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"
    EQUIVALENT = "EQUIVALENT"
    SUPERSEDED = "SUPERSEDED"


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


class CanonicalDomainModel(Protocol):
    def canonical_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TheoryCore:
    hypothesis_space: str
    fundamental_objects: tuple[str, ...]
    declared_symmetries: tuple[str, ...]
    dynamics_kind: str
    assumptions: tuple[str, ...] = ()
    regime_of_validity: str = "UNSPECIFIED"
    unification_claim: str = "UNSPECIFIED"

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_space": self.hypothesis_space,
            "fundamental_objects": sorted(self.fundamental_objects),
            "declared_symmetries": sorted(self.declared_symmetries),
            "dynamics_kind": self.dynamics_kind,
            "assumptions": sorted(self.assumptions),
            "regime_of_validity": self.regime_of_validity,
            "unification_claim": self.unification_claim,
        }


@dataclass(frozen=True)
class ProofObligation:
    proposition: str
    required_scope: str
    allowed_evidence_types: tuple[str, ...]
    allowed_validators: tuple[str, ...] = ()
    weight: float = 1.0


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
    input_hash: str
    details: dict[str, Any] = field(default_factory=dict)
    supersedes: tuple[str, ...] = ()

    @property
    def evidence_id(self) -> str:
        payload = {
            "proposition": self.proposition,
            "scope": self.scope,
            "assumptions": sorted(self.assumptions),
            "method": self.method,
            "status": self.status.value,
            "evidence_type": self.evidence_type,
            "validator_id": self.validator_id,
            "validator_version": self.validator_version,
            "input_hash": self.input_hash,
            "details": self.details,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "EV-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


@dataclass(frozen=True)
class TransitionEvent:
    before: CandidateStatus
    after: CandidateStatus
    evidence_ids: tuple[str, ...]
    rule: str


@dataclass
class CandidateRecord:
    theory: TheoryCore
    domain_model: CanonicalDomainModel
    obligations: list[ProofObligation] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    transformation: str | None = None
    lineage_event_id: str | None = None
    evidence: list[PropositionEvidence] = field(default_factory=list)
    transitions: list[TransitionEvent] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    _status: CandidateStatus = field(default=CandidateStatus.GENERATED, repr=False)

    @property
    def status(self) -> CandidateStatus:
        return self._status

    @property
    def theory_content_id(self) -> str:
        payload = {
            "theory": self.theory.canonical_dict(),
            "domain": self.domain_model.canonical_dict(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "TH-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    @property
    def candidate_instance_id(self) -> str:
        payload = {
            "theory_content_id": self.theory_content_id,
            "parents": sorted(self.parents),
            "transformation": self.transformation,
            "lineage_event_id": self.lineage_event_id,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "CTH-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    def add_evidence(self, item: PropositionEvidence) -> None:
        existing = {e.evidence_id: i for i, e in enumerate(self.evidence)}
        if item.evidence_id in existing:
            self.evidence[existing[item.evidence_id]] = item
        else:
            self.evidence.append(item)

    def active_evidence(self) -> list[PropositionEvidence]:
        superseded = {sid for e in self.evidence for sid in e.supersedes}
        return [e for e in self.evidence if e.evidence_id not in superseded]

    def obligation_discharged(self, obligation: ProofObligation) -> bool:
        matches = [
            e
            for e in self.active_evidence()
            if e.proposition == obligation.proposition
            and e.scope == obligation.required_scope
            and e.evidence_type in obligation.allowed_evidence_types
            and (not obligation.allowed_validators or e.validator_id in obligation.allowed_validators)
        ]
        if any(e.status in {TestStatus.FAIL, TestStatus.REVIEW} for e in matches):
            return False
        return any(e.status is TestStatus.PASS for e in matches)

    def evidence_debt(self) -> float:
        return sum(o.weight for o in self.obligations if not self.obligation_discharged(o))

    def transition(self, target: CandidateStatus) -> None:
        allowed = {
            CandidateStatus.GENERATED: {CandidateStatus.WELL_FORMED, CandidateStatus.REJECTED, CandidateStatus.REVIEW},
            CandidateStatus.WELL_FORMED: {CandidateStatus.STRUCTURALLY_CHECKED, CandidateStatus.REJECTED, CandidateStatus.REVIEW},
            CandidateStatus.STRUCTURALLY_CHECKED: {CandidateStatus.DYNAMICALLY_CHECKED, CandidateStatus.REJECTED, CandidateStatus.REVIEW},
            CandidateStatus.DYNAMICALLY_CHECKED: {CandidateStatus.PREDICTION_REGISTERED, CandidateStatus.REJECTED, CandidateStatus.REVIEW},
            CandidateStatus.PREDICTION_REGISTERED: {CandidateStatus.EMPIRICALLY_COMPARED, CandidateStatus.REVIEW},
            CandidateStatus.EMPIRICALLY_COMPARED: {CandidateStatus.SURVIVES_CURRENT_EVIDENCE, CandidateStatus.REJECTED, CandidateStatus.REVIEW},
        }
        if target not in allowed.get(self._status, set()):
            raise ValueError(f"illegal transition {self._status.value} -> {target.value}")
        required_by_target = {
            CandidateStatus.WELL_FORMED: {"well_formed"},
            CandidateStatus.STRUCTURALLY_CHECKED: {
                "dimensions_consistent",
                "declared_symmetries_respected",
                "kinetic_sign_consistent",
            },
        }
        required = required_by_target.get(target, set())
        obligation_map = {o.proposition: o for o in self.obligations}
        if any(p not in obligation_map or not self.obligation_discharged(obligation_map[p]) for p in required):
            raise ValueError(f"proof obligations not discharged for {target.value}")
        if target in {CandidateStatus.EMPIRICALLY_COMPARED, CandidateStatus.SURVIVES_CURRENT_EVIDENCE}:
            raise ValueError("empirical promotion requires a separate governance layer")
        event = TransitionEvent(
            before=self._status,
            after=target,
            evidence_ids=tuple(sorted(e.evidence_id for e in self.active_evidence())),
            rule="theory-kernel-v2",
        )
        self.transitions.append(event)
        self._status = target

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_instance_id": self.candidate_instance_id,
            "theory_content_id": self.theory_content_id,
            "status": self.status.value,
            "theory": self.theory.canonical_dict(),
            "domain": self.domain_model.canonical_dict(),
            "parents": self.parents,
            "transformation": self.transformation,
            "obligations": [asdict(o) for o in self.obligations],
            "evidence": [asdict(e) | {"evidence_id": e.evidence_id} for e in self.evidence],
            "transitions": [asdict(t) for t in self.transitions],
            "provenance": self.provenance,
        }
