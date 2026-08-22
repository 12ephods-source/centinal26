from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_refs(refs: tuple[str, ...]) -> None:
    if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError("canon records require non-empty provenance_refs")


def _canonical_value(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError("canon value must be JSON-serializable") from exc


@dataclass(frozen=True)
class CanonBranch:
    branch_id: str
    parent_branch_id: str | None
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_id("branch_id", self.branch_id)
        if self.parent_branch_id is not None:
            _require_id("parent_branch_id", self.parent_branch_id)
            if self.parent_branch_id == self.branch_id:
                raise ValueError("branch cannot parent itself")
        _require_refs(self.provenance_refs)


@dataclass(frozen=True)
class CanonFact:
    fact_id: str
    branch_id: str
    entity_id: str
    attribute: str
    value: Any
    provenance_refs: tuple[str, ...]
    supersedes_fact_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("fact_id", self.fact_id),
            ("branch_id", self.branch_id),
            ("entity_id", self.entity_id),
            ("attribute", self.attribute),
        ):
            _require_id(name, value)
        _require_refs(self.provenance_refs)
        _canonical_value(self.value)
        if self.supersedes_fact_id is not None:
            _require_id("supersedes_fact_id", self.supersedes_fact_id)
            if self.supersedes_fact_id == self.fact_id:
                raise ValueError("fact cannot supersede itself")

    @property
    def key(self) -> tuple[str, str]:
        return (self.entity_id, self.attribute)


@dataclass(frozen=True)
class CanonView:
    branch_id: str
    resolved: dict[str, dict[str, Any]]
    contradictions: dict[str, tuple[str, ...]]


class CreativeCanon:
    """Immutable branch/fact registry with explicit supersession and contradictions."""

    def __init__(self) -> None:
        self._branches: dict[str, CanonBranch] = {}
        self._facts: dict[str, CanonFact] = {}

    def add_branch(self, branch: CanonBranch) -> None:
        prior = self._branches.get(branch.branch_id)
        if prior is not None:
            if prior != branch:
                raise ValueError(f"conflicting branch identity: {branch.branch_id}")
            return
        if branch.parent_branch_id is not None and branch.parent_branch_id not in self._branches:
            raise ValueError(f"unknown parent branch: {branch.parent_branch_id}")
        self._branches[branch.branch_id] = branch

    def add_fact(self, fact: CanonFact) -> None:
        prior = self._facts.get(fact.fact_id)
        if prior is not None:
            if prior != fact:
                raise ValueError(f"conflicting fact identity: {fact.fact_id}")
            return
        if fact.branch_id not in self._branches:
            raise ValueError(f"unknown branch: {fact.branch_id}")
        if fact.supersedes_fact_id is not None:
            superseded = self._facts.get(fact.supersedes_fact_id)
            if superseded is None:
                raise ValueError(f"unknown superseded fact: {fact.supersedes_fact_id}")
            if superseded.key != fact.key:
                raise ValueError("supersession must preserve entity and attribute")
            if superseded.branch_id not in self._lineage(fact.branch_id):
                raise ValueError("cannot supersede a fact outside the branch lineage")
        self._facts[fact.fact_id] = fact

    def _lineage(self, branch_id: str) -> tuple[str, ...]:
        if branch_id not in self._branches:
            raise ValueError(f"unknown branch: {branch_id}")
        reverse: list[str] = []
        current: str | None = branch_id
        while current is not None:
            reverse.append(current)
            current = self._branches[current].parent_branch_id
        return tuple(reversed(reverse))

    def view(self, branch_id: str) -> CanonView:
        lineage = set(self._lineage(branch_id))
        visible = [fact for fact in self._facts.values() if fact.branch_id in lineage]
        superseded_ids = {
            fact.supersedes_fact_id
            for fact in visible
            if fact.supersedes_fact_id is not None
        }
        active = [fact for fact in visible if fact.fact_id not in superseded_ids]

        grouped: dict[tuple[str, str], list[CanonFact]] = {}
        for fact in active:
            grouped.setdefault(fact.key, []).append(fact)

        resolved: dict[str, dict[str, Any]] = {}
        contradictions: dict[str, tuple[str, ...]] = {}
        for (entity_id, attribute), facts in sorted(grouped.items()):
            values = {_canonical_value(fact.value) for fact in facts}
            key = f"{entity_id}.{attribute}"
            if len(values) > 1:
                contradictions[key] = tuple(sorted(fact.fact_id for fact in facts))
                continue
            chosen = min(facts, key=lambda fact: fact.fact_id)
            resolved.setdefault(entity_id, {})[attribute] = chosen.value
        return CanonView(branch_id=branch_id, resolved=resolved, contradictions=contradictions)

    def facts(self) -> tuple[CanonFact, ...]:
        return tuple(self._facts[key] for key in sorted(self._facts))

    def branches(self) -> tuple[CanonBranch, ...]:
        return tuple(self._branches[key] for key in sorted(self._branches))
