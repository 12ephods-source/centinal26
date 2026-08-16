"""Preservation-first visual optimization controller.

Provider-neutral orchestration for iterative image improvement. It deliberately
separates candidate generation from promotion: rejected candidates never become
parents. Providers implement VisualProvider; policy/state remain canonical here.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Defect:
    key: str
    instruction: str


@dataclass(frozen=True)
class Scores:
    preservation: float
    target_gain: float
    collateral_drift: float


@dataclass(frozen=True)
class Candidate:
    artifact: str
    scores: Scores
    evidence: dict


@dataclass(frozen=True)
class Policy:
    min_preservation: float = 0.92
    min_target_gain: float = 0.01
    max_collateral_drift: float = 0.08
    max_iterations: int = 32


class VisualProvider(Protocol):
    def generate(self, *, canonical_artifact: str, defect: Defect, locks: Sequence[str]) -> str: ...
    def evaluate(self, *, canonical_artifact: str, candidate_artifact: str, defect: Defect, locks: Sequence[str]) -> Candidate: ...


DEFAULT_DRAGONIA_QUEUE = (
    Defect("white_dragon_cardinality", "Upper-right background only: consolidate duplicate white-dragon heads into exactly one coherent white dragon. Add nothing else."),
    Defect("reidrick_identity_orientation", "Correct Reidrick only: human-scale silver dragonborn, lower behind Aldrick, back toward viewer, head turned left/up."),
    Defect("reidrick_attack_edge", "Correct only Reidrick's attack: blue-white lightning originates visibly inside his mouth and terminates on the red dragon."),
    Defect("grumm_attack_edge", "Correct only Grumm's attack: one narrow green beam originates at the central pupil and terminates on the single white dragon."),
    Defect("cumulus_scale", "Reduce and distance Cumulus only; preserve foreground and castle composition."),
    Defect("combat_cues", "Add only minimal combat cues to already-locked foreground poses; do not reposition or redesign characters."),
    Defect("chariot_motion", "Improve only chariot upward/toward-viewer motion via subtle foreshortening, taut harness lines and directional atmosphere."),
    Defect("atmospheric_depth", "Improve only background atmospheric separation; preserve foreground rendering and geometry."),
)

DRAGONIA_LOCKS = (
    "Aldrick identity, face, hair, anatomy, armor, amulet, pose and relative position",
    "all four women: identities, faces, anatomy, hair, costumes, expressions, poses, overlaps and relative positions",
    "foreground intimacy and triangular grouping",
    "dragon-prowed chariot and pixies unless the active defect explicitly targets chariot mechanics",
    "rendering style, lighting character, framing and color grade",
    "no new characters, creatures, weapons or spell sources",
)


def accepted(scores: Scores, policy: Policy) -> bool:
    return (
        scores.preservation >= policy.min_preservation
        and scores.target_gain >= policy.min_target_gain
        and scores.collateral_drift <= policy.max_collateral_drift
    )


def _hash_record(record: dict) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


class VisualOptimizer:
    def __init__(self, provider: VisualProvider, ledger_path: str | Path, policy: Policy = Policy()):
        self.provider = provider
        self.ledger_path = Path(ledger_path)
        self.policy = policy

    def optimize(self, canonical_artifact: str, defects: Sequence[Defect] = DEFAULT_DRAGONIA_QUEUE,
                 locks: Sequence[str] = DRAGONIA_LOCKS) -> str:
        """Run bounded coordinate descent. Every candidate starts from the last *accepted*
        canonical artifact; rejection leaves canonical unchanged. Stops at queue exhaustion
        or policy.max_iterations. Returns the promoted canonical artifact reference.
        """
        current = canonical_artifact
        previous_hash = "GENESIS"
        iteration = 0
        for defect in defects:
            if iteration >= self.policy.max_iterations:
                break
            iteration += 1
            candidate_ref = self.provider.generate(canonical_artifact=current, defect=defect, locks=locks)
            candidate = self.provider.evaluate(
                canonical_artifact=current,
                candidate_artifact=candidate_ref,
                defect=defect,
                locks=locks,
            )
            promote = accepted(candidate.scores, self.policy)
            record = {
                "iteration": iteration,
                "defect": asdict(defect),
                "parent": current,
                "candidate": candidate.artifact,
                "scores": asdict(candidate.scores),
                "decision": "PROMOTE" if promote else "REJECT",
                "evidence": candidate.evidence,
                "prev_hash": previous_hash,
            }
            record["record_hash"] = _hash_record(record)
            self._append(record)
            previous_hash = record["record_hash"]
            if promote:
                current = candidate.artifact
        return current

    def _append(self, record: dict) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
