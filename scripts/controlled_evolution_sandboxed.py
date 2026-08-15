from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import controlled_evolution_loop as loop
from centinal26.evolution_sandbox import EvolutionDockerEvaluator
from centinal26.hard_sandbox import SandboxLimits, SandboxUnavailable

DEFAULT_IMAGE = "centinal26-evolution-validator:local"
PYTHON_IN_IMAGE = "/usr/local/bin/python"


def evaluator() -> EvolutionDockerEvaluator:
    return EvolutionDockerEvaluator(
        image=os.environ.get("CENTINAL26_SANDBOX_IMAGE", DEFAULT_IMAGE)
    )


def validator_versions(name: str) -> dict[str, str]:
    return {
        "adapter": "centinal26-evolution-docker/1",
        "python": os.environ.get("CENTINAL26_SANDBOX_PYTHON_VERSION", "3.13"),
        "pytest": os.environ.get("CENTINAL26_SANDBOX_PYTEST_VERSION", "9.1.1"),
        "validator": name,
    }


def sandbox_limits(timeout: int) -> SandboxLimits:
    return SandboxLimits(
        cpu_seconds=max(1, min(timeout, 300)),
        memory_bytes=768 * 1024 * 1024,
        processes=64,
        wall_seconds=float(timeout),
        output_bytes=256 * 1024,
        open_files=128,
        cpus=1.0,
        tmp_bytes=128 * 1024 * 1024,
    )


def image_command(command: list[str]) -> list[str]:
    if command and command[0] == sys.executable:
        return [PYTHON_IN_IMAGE, *command[1:]]
    return list(command)


def evaluate_with_commit(
    worktree: Path,
    goal: loop.GoalSpec,
    candidate_commit: str,
) -> tuple[bool, float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    score = 0.0
    passed = True
    runner = evaluator()

    for name, command, timeout, weight in loop.validator_commands(goal):
        try:
            result = runner.evaluate(
                worktree,
                candidate_commit=candidate_commit,
                goal_digest=goal.digest(),
                command=image_command(command),
                validator_versions=validator_versions(name),
                limits=sandbox_limits(timeout),
            )
        except SandboxUnavailable as error:
            results.append(
                {
                    "name": name,
                    "passed": False,
                    "output": f"SANDBOX_UNAVAILABLE: {error}",
                    "sandbox_status": "BLOCKED",
                    "host_execution_fallback": False,
                    "candidate_commit": candidate_commit,
                }
            )
            passed = False
            break

        ok = (
            result.exit_code == 0
            and not result.timed_out
            and not result.output_limited
        )
        combined_output = result.stdout + result.stderr
        results.append(
            {
                "name": name,
                "passed": ok,
                "output": combined_output[-8000:],
                "sandbox_status": "EXECUTED",
                "sandbox": result.as_dict(),
            }
        )
        if ok:
            score += weight
        else:
            passed = False

    return passed, round(score, 6), results


def sandboxed_evaluate(
    worktree: Path,
    goal: loop.GoalSpec,
) -> tuple[bool, float, list[dict[str, Any]]]:
    commit = loop.git(worktree, "rev-parse", "HEAD")
    return evaluate_with_commit(worktree, goal, commit)


def sandboxed_evaluate_candidate(
    repo: Path,
    goal: loop.GoalSpec,
    state_dir: Path,
    temp_root: Path,
    base_commit: str,
    candidate_id: str,
    patch: str,
) -> loop.CandidateEvidence:
    policy_reasons = loop.patch_policy(goal, patch)
    if policy_reasons:
        return loop.rejected_candidate(
            candidate_id,
            base_commit,
            ";".join(policy_reasons),
            patch,
        )

    worktree = temp_root / candidate_id
    loop.create_worktree(repo, base_commit, worktree)
    try:
        patch_file = state_dir / "patches" / f"{candidate_id}.diff"
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(patch, encoding="utf-8")
        applied = loop.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_file)],
            worktree,
        )
        if applied.returncode != 0:
            return loop.rejected_candidate(
                candidate_id,
                base_commit,
                "git_apply_failed",
                patch,
            )

        paths = loop.changed_paths(worktree)
        if not paths:
            return loop.rejected_candidate(candidate_id, base_commit, "no_effect", patch)

        reasons: list[str] = []
        for relative in paths:
            try:
                permitted, reason = goal.permits_changed_path(relative)
            except ValueError:
                permitted, reason = False, "unsafe_path"
            if not permitted:
                reasons.append(f"path_denied:{relative}:{reason}")
        if reasons:
            return loop.rejected_candidate(
                candidate_id,
                base_commit,
                ";".join(reasons),
                patch,
            )

        before = loop.snapshot_paths(worktree, paths)
        security_decision, security_reasons = loop.audit_changed_tree(
            repo,
            worktree,
            paths,
            state_dir,
            candidate_id,
        )
        if security_decision != "ALLOW_STATIC_ONLY" or security_reasons:
            reason = ";".join(security_reasons) or f"security:{security_decision}"
            return loop.CandidateEvidence(
                candidate_id=candidate_id,
                agent="goose-chat-patch-only",
                base_commit=base_commit,
                patch_sha256=loop.canonical_sha256(patch),
                changed_paths=tuple(paths),
                security_decision=security_decision,
                validation_passed=False,
                validation_results=(),
                score=0.0,
                rejection_reasons=(reason,),
            )

        # Freeze the exact audited candidate before any untrusted execution. The
        # local commit is not promoted merely by existing; it is used as an
        # immutable identity for sandbox evidence and is selected only after PASS.
        candidate_commit = loop.commit_candidate(worktree, candidate_id, paths)
        validation_passed, score, validation_results = evaluate_with_commit(
            worktree,
            goal,
            candidate_commit,
        )

        after_paths = loop.changed_paths(worktree)
        after = loop.snapshot_paths(worktree, paths)
        side_effect = bool(after_paths) or after != before
        rejection_reasons: list[str] = []
        if side_effect:
            rejection_reasons.append("worktree_changed_during_evaluation")
        if not validation_passed:
            rejection_reasons.append("validation_failed")

        return loop.CandidateEvidence(
            candidate_id=candidate_id,
            agent="goose-chat-patch-only",
            base_commit=base_commit,
            patch_sha256=loop.canonical_sha256(patch),
            changed_paths=tuple(paths),
            security_decision=security_decision,
            validation_passed=validation_passed and not side_effect,
            validation_results=tuple(validation_results),
            score=score,
            commit=(
                candidate_commit
                if validation_passed and not rejection_reasons
                else None
            ),
            rejection_reasons=tuple(rejection_reasons),
        )
    finally:
        loop.remove_worktree(repo, worktree)


def main() -> int:
    runner = evaluator()
    try:
        image_id = runner.image_id()
        runner.probe()
    except SandboxUnavailable as error:
        print(
            f"BLOCKED: hard evolution sandbox unavailable: {error}; host fallback is disabled",
            file=sys.stderr,
        )
        return 4

    print(f"controlled-evolution sandbox image: {image_id}", file=sys.stderr)
    loop.evaluate = sandboxed_evaluate
    loop.evaluate_candidate = sandboxed_evaluate_candidate
    return loop.main()


if __name__ == "__main__":
    raise SystemExit(main())
