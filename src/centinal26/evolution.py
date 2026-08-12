from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

GOAL_SCHEMA = "centinal26-goal-v1"
STATE_SCHEMA = "centinal26-evolution-state-v1"
CYCLE_SCHEMA = "centinal26-evolution-cycle-v1"

DEFAULT_PROTECTED_PREFIXES = (
    ".github/",
    ".git/",
    "goals/",
    "tests/",
    "schemas/",
    "provenance/",
    "releases/",
    "security/",
    "termux/",
    "SECURITY.md",
    "pyproject.toml",
    "src/centinal26/core.py",
    "src/centinal26/evolution.py",
    "scripts/audit_untrusted_candidate.py",
    "scripts/controlled_evolution_loop.py",
    "scripts/run-controlled-evolution.sh",
)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise ValueError(f"unsafe repository path: {value!r}")
    return path.as_posix()


def slug(value: str) -> str:
    rendered = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not rendered:
        raise ValueError("goal_id must contain an alphanumeric character")
    return rendered[:64]


@dataclass(frozen=True)
class GoalSpec:
    goal_id: str
    objective: str
    include_paths: tuple[str, ...]
    goal_tests: tuple[str, ...]
    allowed_change_prefixes: tuple[str, ...]
    protected_prefixes: tuple[str, ...] = DEFAULT_PROTECTED_PREFIXES
    max_cycles: int = 6
    candidates_per_cycle: int = 3
    max_agent_turns: int = 24
    max_context_bytes: int = 180_000
    max_patch_bytes: int = 120_000

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GoalSpec":
        if value.get("schema") != GOAL_SCHEMA:
            raise ValueError(f"goal schema must be {GOAL_SCHEMA}")
        objective = value.get("objective")
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("objective must be non-empty text")
        goal_id = slug(str(value.get("goal_id", "")))

        def paths(name: str) -> tuple[str, ...]:
            raw = value.get(name, [])
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise ValueError(f"{name} must be a list of repository paths")
            return tuple(safe_relative_path(item) for item in raw)

        include_paths = paths("include_paths")
        goal_tests = paths("goal_tests")
        allowed = paths("allowed_change_prefixes")
        protected = tuple(DEFAULT_PROTECTED_PREFIXES) + paths(
            "additional_protected_prefixes"
        )
        if not include_paths:
            raise ValueError("include_paths may not be empty")
        if not goal_tests:
            raise ValueError("goal_tests may not be empty")
        if not allowed:
            raise ValueError("allowed_change_prefixes may not be empty")
        if any(not item.startswith("tests/") for item in goal_tests):
            raise ValueError("goal_tests must live under tests/")
        for test_path in goal_tests:
            if not any(
                test_path == prefix.rstrip("/") or test_path.startswith(prefix)
                for prefix in protected
            ):
                raise ValueError("goal tests must be protected from candidate edits")

        max_cycles = int(value.get("max_cycles", 6))
        candidates = int(value.get("candidates_per_cycle", 3))
        max_turns = int(value.get("max_agent_turns", 24))
        context_bytes = int(value.get("max_context_bytes", 180_000))
        patch_bytes = int(value.get("max_patch_bytes", 120_000))
        if not 1 <= max_cycles <= 50:
            raise ValueError("max_cycles must be between 1 and 50")
        if not 1 <= candidates <= 8:
            raise ValueError("candidates_per_cycle must be between 1 and 8")
        if not 1 <= max_turns <= 100:
            raise ValueError("max_agent_turns must be between 1 and 100")
        if not 10_000 <= context_bytes <= 1_000_000:
            raise ValueError("max_context_bytes out of range")
        if not 1_000 <= patch_bytes <= 500_000:
            raise ValueError("max_patch_bytes out of range")

        return cls(
            goal_id=goal_id,
            objective=objective.strip(),
            include_paths=include_paths,
            goal_tests=goal_tests,
            allowed_change_prefixes=allowed,
            protected_prefixes=protected,
            max_cycles=max_cycles,
            candidates_per_cycle=candidates,
            max_agent_turns=max_turns,
            max_context_bytes=context_bytes,
            max_patch_bytes=patch_bytes,
        )

    @classmethod
    def load(cls, path: Path) -> "GoalSpec":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def digest(self) -> str:
        return canonical_sha256(asdict(self))

    def permits_changed_path(self, path: str) -> tuple[bool, str]:
        normalized = safe_relative_path(path)
        for prefix in self.protected_prefixes:
            clean = prefix.rstrip("/")
            if normalized == clean or normalized.startswith(clean + "/"):
                return False, f"protected:{prefix}"
        if not any(
            normalized == prefix.rstrip("/")
            or normalized.startswith(prefix.rstrip("/") + "/")
            for prefix in self.allowed_change_prefixes
        ):
            return False, "outside_allowed_change_prefixes"
        return True, "allowed"


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    agent: str
    base_commit: str
    patch_sha256: str
    changed_paths: tuple[str, ...]
    security_decision: str
    validation_passed: bool
    validation_results: tuple[dict[str, Any], ...]
    score: float
    commit: str | None = None
    rejection_reasons: tuple[str, ...] = ()


@dataclass
class EvolutionState:
    goal_id: str
    goal_sha256: str
    generation: int
    active_commit: str
    active_branch: str
    best_score: float = 0.0
    status: str = "ACTIVE"
    cycles: list[str] = field(default_factory=list)

    @classmethod
    def load_or_create(
        cls,
        path: Path,
        goal_id: str,
        goal_sha256: str,
        base_commit: str,
    ) -> "EvolutionState":
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema") != STATE_SCHEMA or value.get("goal_id") != goal_id:
                raise ValueError("evolution state schema/goal mismatch")
            if value.get("goal_sha256") != goal_sha256:
                raise ValueError(
                    "goal/evaluator digest changed; start a new goal_id instead of mutating fitness"
                )
            return cls(
                goal_id=value["goal_id"],
                goal_sha256=value["goal_sha256"],
                generation=int(value["generation"]),
                active_commit=value["active_commit"],
                active_branch=value["active_branch"],
                best_score=float(value.get("best_score", 0.0)),
                status=value.get("status", "ACTIVE"),
                cycles=list(value.get("cycles", [])),
            )
        return cls(
            goal_id=goal_id,
            goal_sha256=goal_sha256,
            generation=0,
            active_commit=base_commit,
            active_branch=f"evolution/{goal_id}/g0000",
        )

    def to_dict(self) -> dict[str, Any]:
        return {"schema": STATE_SCHEMA, **asdict(self)}


@dataclass(frozen=True)
class CycleEvidence:
    goal_id: str
    goal_sha256: str
    generation: int
    parent_commit: str
    baseline_score: float
    candidates: tuple[CandidateEvidence, ...]
    decision: str
    selected_candidate: str | None
    selected_commit: str | None

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schema": CYCLE_SCHEMA,
            "goal_id": self.goal_id,
            "goal_sha256": self.goal_sha256,
            "generation": self.generation,
            "parent_commit": self.parent_commit,
            "baseline_score": self.baseline_score,
            "candidates": [asdict(item) for item in self.candidates],
            "decision": self.decision,
            "selected_candidate": self.selected_candidate,
            "selected_commit": self.selected_commit,
        }
        value["sha256"] = canonical_sha256(value)
        return value


def select_candidate(
    candidates: list[CandidateEvidence],
    baseline_score: float,
) -> CandidateEvidence | None:
    eligible = [
        item
        for item in candidates
        if item.validation_passed
        and item.security_decision == "ALLOW_STATIC_ONLY"
        and not item.rejection_reasons
        and item.commit is not None
        and item.score > baseline_score
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (item.score, -len(item.changed_paths), item.candidate_id),
    )
