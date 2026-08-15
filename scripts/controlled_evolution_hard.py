from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from centinal26.evolution import CandidateEvidence, canonical_sha256
from centinal26.evolution_sandbox import evaluate_in_hard_sandbox
from centinal26.hard_sandbox import SandboxUnavailable

HARD_PROTECTED_PATHS = (
    "src/centinal26/hard_sandbox.py",
    "src/centinal26/evolution_sandbox.py",
    "scripts/controlled_evolution_hard.py",
    "scripts/controlled_evolution_loop.py",
    "scripts/run-controlled-evolution.sh",
)


class EvolutionSandboxBlocked(BaseException):
    """Non-catchable-by-legacy-candidate-loop hard block for sandbox failure."""


def _load_legacy() -> ModuleType:
    path = Path(__file__).with_name("controlled_evolution_loop.py")
    spec = importlib.util.spec_from_file_location("centinal26_controlled_evolution_legacy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load controlled evolution implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hard_protection_reasons(legacy: ModuleType, patch: str) -> list[str]:
    reasons: list[str] = []
    changed = legacy.patch_paths(patch)
    for path in changed:
        for protected in HARD_PROTECTED_PATHS:
            if path == protected or path.startswith(protected.rstrip("/") + "/"):
                reasons.append(f"hard_evaluator_path_denied:{path}")
    return reasons


def _hard_evaluate(legacy: ModuleType, worktree: Path, goal: Any):
    commit = legacy.git(worktree, "rev-parse", "HEAD")
    try:
        return evaluate_in_hard_sandbox(
            worktree,
            candidate_commit=commit,
            goal_digest=goal.digest(),
            goal_tests=goal.goal_tests,
        )
    except SandboxUnavailable as error:
        raise EvolutionSandboxBlocked(str(error)) from error


def _hard_evaluate_candidate(
    legacy: ModuleType,
    repo: Path,
    goal: Any,
    state_dir: Path,
    temp_root: Path,
    base_commit: str,
    candidate_id: str,
    patch: str,
) -> CandidateEvidence:
    policy_reasons = list(legacy.patch_policy(goal, patch))
    policy_reasons.extend(_hard_protection_reasons(legacy, patch))
    if policy_reasons:
        return legacy.rejected_candidate(
            candidate_id,
            base_commit,
            ";".join(sorted(set(policy_reasons))),
            patch,
        )

    worktree = temp_root / candidate_id
    legacy.create_worktree(repo, base_commit, worktree)
    try:
        patch_file = state_dir / "patches" / f"{candidate_id}.diff"
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(patch, encoding="utf-8")
        applied = legacy.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_file)],
            worktree,
        )
        if applied.returncode != 0:
            return legacy.rejected_candidate(
                candidate_id,
                base_commit,
                "git_apply_failed",
                patch,
            )

        paths = legacy.changed_paths(worktree)
        if not paths:
            return legacy.rejected_candidate(candidate_id, base_commit, "no_effect", patch)

        reasons: list[str] = []
        for relative in paths:
            if relative in HARD_PROTECTED_PATHS:
                reasons.append(f"hard_evaluator_path_denied:{relative}")
                continue
            try:
                permitted, reason = goal.permits_changed_path(relative)
            except ValueError:
                permitted, reason = False, "unsafe_path"
            if not permitted:
                reasons.append(f"path_denied:{relative}:{reason}")
        if reasons:
            return legacy.rejected_candidate(
                candidate_id,
                base_commit,
                ";".join(reasons),
                patch,
            )

        before = legacy.snapshot_paths(worktree, paths)
        security_decision, security_reasons = legacy.audit_changed_tree(
            repo,
            worktree,
            paths,
            state_dir,
            candidate_id,
        )
        if security_decision != "ALLOW_STATIC_ONLY" or security_reasons:
            reason = ";".join(security_reasons) or f"security:{security_decision}"
            return CandidateEvidence(
                candidate_id=candidate_id,
                agent="goose-chat-patch-only",
                base_commit=base_commit,
                patch_sha256=canonical_sha256(patch),
                changed_paths=tuple(paths),
                security_decision=security_decision,
                validation_passed=False,
                validation_results=(),
                score=0.0,
                rejection_reasons=(reason,),
            )

        # Commit the audited patch in the detached candidate worktree before executing
        # validators, so the sandbox evidence can bind the exact candidate commit.
        candidate_commit = legacy.commit_candidate(worktree, candidate_id, paths)
        try:
            validation_passed, score, validation_results = evaluate_in_hard_sandbox(
                worktree,
                candidate_commit=candidate_commit,
                goal_digest=goal.digest(),
                goal_tests=goal.goal_tests,
            )
        except SandboxUnavailable as error:
            raise EvolutionSandboxBlocked(str(error)) from error

        after = legacy.snapshot_paths(worktree, paths)
        dirty = bool(legacy.git(worktree, "status", "--porcelain=v1"))
        side_effect = dirty or after != before
        rejection_reasons: list[str] = []
        if side_effect:
            rejection_reasons.append("worktree_changed_during_evaluation")
        if not validation_passed:
            rejection_reasons.append("validation_failed")

        return CandidateEvidence(
            candidate_id=candidate_id,
            agent="goose-chat-patch-only",
            base_commit=base_commit,
            patch_sha256=canonical_sha256(patch),
            changed_paths=tuple(paths),
            security_decision=security_decision,
            validation_passed=validation_passed and not side_effect,
            validation_results=tuple(validation_results),
            score=score,
            commit=candidate_commit if validation_passed and not side_effect else None,
            rejection_reasons=tuple(rejection_reasons),
        )
    finally:
        legacy.remove_worktree(repo, worktree)


def main() -> int:
    legacy = _load_legacy()
    legacy.evaluate = lambda worktree, goal: _hard_evaluate(legacy, worktree, goal)
    legacy.evaluate_candidate = (
        lambda repo, goal, state_dir, temp_root, base_commit, candidate_id, patch: (
            _hard_evaluate_candidate(
                legacy,
                repo,
                goal,
                state_dir,
                temp_root,
                base_commit,
                candidate_id,
                patch,
            )
        )
    )
    try:
        return int(legacy.main())
    except EvolutionSandboxBlocked as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_HARD_SANDBOX",
                    "reason": str(error),
                    "host_execution_fallback": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
