from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path
from typing import Any

from centinal26.evolution import (
    CandidateEvidence,
    CycleEvidence,
    EvolutionState,
    GoalSpec,
    canonical_sha256,
    select_candidate,
)

STRATEGIES = (
    "minimal-diff",
    "robustness",
    "alternative-design",
    "simplification",
    "adversarial-edge-cases",
    "performance",
    "compatibility",
    "recovery",
)


def run(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def git(root: Path, *args: str, timeout: int = 120) -> str:
    result = run(["git", *args], root, timeout=timeout)
    if result.returncode != 0:
        joined = " ".join(args)
        raise RuntimeError(f"git {joined} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout.strip()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_clean_repo(root: Path) -> None:
    if git(root, "status", "--porcelain=v1"):
        raise RuntimeError("repository must be clean before controlled evolution")


def create_worktree(repo: Path, commit: str, path: Path) -> None:
    result = run(["git", "worktree", "add", "--detach", str(path), commit], repo)
    if result.returncode != 0:
        raise RuntimeError(f"worktree creation failed: {result.stdout}")


def remove_worktree(repo: Path, path: Path) -> None:
    result = run(["git", "worktree", "remove", "--force", str(path)], repo)
    if result.returncode != 0:
        run(["git", "worktree", "prune"], repo)


def context_files(root: Path, goal: GoalSpec) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for relative in goal.include_paths:
        path = root / relative
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in candidates:
            if not candidate.is_file() or ".git" in candidate.parts:
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(candidate)
    return result


def build_context(root: Path, goal: GoalSpec) -> str:
    blocks: list[str] = []
    used = 0
    for path in context_files(root, goal):
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:4096]:
                continue
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        block = f"\n===== FILE: {relative} =====\n{text}\n"
        encoded = block.encode()
        if used + len(encoded) > goal.max_context_bytes:
            remaining = goal.max_context_bytes - used
            if remaining > 1000:
                blocks.append(encoded[:remaining].decode("utf-8", errors="ignore"))
            break
        blocks.append(block)
        used += len(encoded)
    if not blocks:
        raise RuntimeError("goal context contains no readable files")
    return "".join(blocks)


def build_locked_tests(root: Path, goal: GoalSpec) -> str:
    blocks: list[str] = []
    for relative in goal.goal_tests:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"locked goal test missing: {relative}")
        blocks.append(
            f"\n===== LOCKED EVALUATOR: {relative} =====\n"
            f"{path.read_text(encoding='utf-8')}\n"
        )
    return "".join(blocks)


def extract_patch(text: str) -> str:
    fenced = re.findall(
        r"```(?:diff|patch)?\s*\n(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for candidate in fenced or [text]:
        start = candidate.find("diff --git ")
        if start < 0:
            continue
        patch = candidate[start:].strip() + "\n"
        if "--- " in patch and "+++ " in patch:
            return patch
    raise ValueError("agent did not return a unified git diff")


def patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for prefix in ("--- a/", "+++ b/"):
        pattern = rf"^{re.escape(prefix)}(.+)$"
        for match in re.finditer(pattern, patch, flags=re.MULTILINE):
            value = match.group(1).strip()
            if value != "/dev/null" and value not in paths:
                paths.append(value)
    return sorted(paths)


def patch_policy(goal: GoalSpec, patch: str) -> list[str]:
    reasons: list[str] = []
    if len(patch.encode()) > goal.max_patch_bytes:
        reasons.append("patch_too_large")
    if "GIT binary patch" in patch or "Binary files " in patch:
        reasons.append("binary_patch_denied")
    paths = patch_paths(patch)
    if not paths:
        reasons.append("no_changed_paths")
    for path in paths:
        try:
            permitted, reason = goal.permits_changed_path(path)
        except ValueError:
            reasons.append(f"unsafe_path:{path}")
            continue
        if not permitted:
            reasons.append(f"path_denied:{path}:{reason}")
    return reasons


def proposal_environment(candidate_id: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "GOOSE_MODE": "chat",
        "SECURITY_PROMPT_ENABLED": "true",
        "GOOSE_PATH_ROOT": str(
            Path(tempfile.gettempdir()) / f"centinal26-goose-{candidate_id}"
        ),
    }
    for name in (
        "GOOSE_PROVIDER",
        "GOOSE_MODEL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def goose_patch(
    parent_tree: Path,
    goal: GoalSpec,
    context: str,
    locked_tests: str,
    strategy: str,
    candidate_id: str,
) -> str:
    prompt = textwrap.dedent(
        f"""
        You are a patch-only mutation proposer in a controlled software-evolution system.

        OBJECTIVE:
        {goal.objective}

        STRATEGY: {strategy}

        HARD RULES:
        - Return exactly one unified git diff beginning with `diff --git`.
        - Do not invoke tools, shell commands, network requests, or package installers.
        - Use only the supplied repository context and locked evaluators.
        - Never edit tests, CI, provenance, releases, Termux control, security policy,
          authorization logic, audit logic, goal definitions, or evolution control code.
        - Only modify paths under: {', '.join(goal.allowed_change_prefixes)}
        - Never weaken validation or add credential access, persistence, privilege
          escalation, remote-script execution, obfuscation, or destructive behavior.
        - If a safe patch cannot be derived, return no patch instead of inventing evidence.

        LOCKED EVALUATORS:
        {locked_tests}

        REPOSITORY CONTEXT:
        {context}
        """
    ).strip()
    result = run(
        [
            "goose",
            "run",
            "--no-session",
            "--max-turns",
            str(goal.max_agent_turns),
            "--output-format",
            "text",
            "-q",
            "-t",
            prompt,
        ],
        parent_tree,
        env=proposal_environment(candidate_id),
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"goose failed ({result.returncode}): {result.stdout[-2000:]}")
    return extract_patch(result.stdout)


def changed_paths(worktree: Path) -> list[str]:
    tracked = git(worktree, "diff", "--name-only", "--no-renames", "HEAD")
    untracked = git(worktree, "ls-files", "--others", "--exclude-standard")
    return sorted({line for line in (tracked + "\n" + untracked).splitlines() if line})


def snapshot_paths(worktree: Path, paths: list[str]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for relative in paths:
        path = worktree / relative
        snapshot[relative] = file_sha256(path) if path.is_file() else "DELETED"
    return snapshot


def audit_changed_tree(
    repo: Path,
    worktree: Path,
    paths: list[str],
    state_dir: Path,
    candidate_id: str,
) -> tuple[str, list[str]]:
    archive = state_dir / "audits" / f"{candidate_id}.zip"
    report = state_dir / "audits" / f"{candidate_id}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for relative in paths:
            path = worktree / relative
            if path.is_file():
                output.write(path, relative)
    auditor = repo / "scripts" / "audit_untrusted_candidate.py"
    result = run(
        [sys.executable, str(auditor), str(archive), "--output", str(report)],
        repo,
        timeout=60,
    )
    try:
        value = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "DENY", ["security_report_invalid"]
    reasons = [
        f"security:{item.get('severity')}:{item.get('rule')}:{item.get('path')}"
        for item in value.get("findings", [])
        if item.get("severity") in {"critical", "high"}
    ]
    if result.returncode != 0 and not reasons:
        reasons.append(f"security_audit_failed:{value.get('reason')}")
    return str(value.get("decision", "DENY")), reasons


def validator_commands(goal: GoalSpec) -> tuple[tuple[str, list[str], int, float], ...]:
    return (
        (
            "goal_tests",
            [sys.executable, "-m", "pytest", "-q", *goal.goal_tests],
            300,
            0.70,
        ),
        (
            "repository_invariants",
            [sys.executable, "tests/validate_repository.py"],
            180,
            0.20,
        ),
        (
            "compile",
            [sys.executable, "-m", "compileall", "-q", "src", "scripts"],
            180,
            0.10,
        ),
    )


def evaluate(worktree: Path, goal: GoalSpec) -> tuple[bool, float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    score = 0.0
    passed = True
    with tempfile.TemporaryDirectory(prefix="centinal26-eval-home-") as home:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": home,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PYTHONPATH": str(worktree / "src"),
            "CENTINAL26_EVOLUTION_EVALUATION": "1",
        }
        for name, command, timeout, weight in validator_commands(goal):
            try:
                result = run(command, worktree, env=env, timeout=timeout)
                ok = result.returncode == 0
                output = result.stdout[-8000:]
            except subprocess.TimeoutExpired as error:
                ok = False
                output = f"TIMEOUT after {timeout}s: {error}"
            results.append({"name": name, "passed": ok, "output": output})
            if ok:
                score += weight
            else:
                passed = False
    return passed, round(score, 6), results


def commit_candidate(worktree: Path, candidate_id: str, paths: list[str]) -> str:
    git(worktree, "add", "--", *paths)
    staged = sorted(git(worktree, "diff", "--cached", "--name-only").splitlines())
    if staged != sorted(paths):
        raise RuntimeError("staged paths differ from audited paths")
    result = run(
        [
            "git",
            "-c",
            "user.name=Centinal26 Controlled Evolution",
            "-c",
            "user.email=controlled-evolution@localhost",
            "commit",
            "-m",
            f"evolution candidate {candidate_id}",
        ],
        worktree,
    )
    if result.returncode != 0:
        raise RuntimeError(f"candidate commit failed: {result.stdout}")
    return git(worktree, "rev-parse", "HEAD")


def rejected_candidate(
    candidate_id: str,
    base_commit: str,
    reason: str,
    patch: str = "",
) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=candidate_id,
        agent="goose-chat-patch-only",
        base_commit=base_commit,
        patch_sha256=canonical_sha256(patch) if patch else "0" * 64,
        changed_paths=(),
        security_decision="NOT_RUN",
        validation_passed=False,
        validation_results=(),
        score=0.0,
        rejection_reasons=(reason,),
    )


def evaluate_candidate(
    repo: Path,
    goal: GoalSpec,
    state_dir: Path,
    temp_root: Path,
    base_commit: str,
    candidate_id: str,
    patch: str,
) -> CandidateEvidence:
    policy_reasons = patch_policy(goal, patch)
    if policy_reasons:
        return rejected_candidate(
            candidate_id,
            base_commit,
            ";".join(policy_reasons),
            patch,
        )

    worktree = temp_root / candidate_id
    create_worktree(repo, base_commit, worktree)
    try:
        patch_file = state_dir / "patches" / f"{candidate_id}.diff"
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(patch, encoding="utf-8")
        applied = run(
            ["git", "apply", "--whitespace=nowarn", str(patch_file)],
            worktree,
        )
        if applied.returncode != 0:
            return rejected_candidate(
                candidate_id,
                base_commit,
                "git_apply_failed",
                patch,
            )

        paths = changed_paths(worktree)
        if not paths:
            return rejected_candidate(candidate_id, base_commit, "no_effect", patch)
        reasons: list[str] = []
        for relative in paths:
            try:
                permitted, reason = goal.permits_changed_path(relative)
            except ValueError:
                permitted, reason = False, "unsafe_path"
            if not permitted:
                reasons.append(f"path_denied:{relative}:{reason}")
        if reasons:
            return rejected_candidate(
                candidate_id,
                base_commit,
                ";".join(reasons),
                patch,
            )

        before = snapshot_paths(worktree, paths)
        security_decision, security_reasons = audit_changed_tree(
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

        validation_passed, score, validation_results = evaluate(worktree, goal)
        after_paths = changed_paths(worktree)
        after = snapshot_paths(worktree, paths)
        side_effect = after_paths != paths or after != before
        reasons = []
        if side_effect:
            reasons.append("worktree_changed_during_evaluation")
        if not validation_passed:
            reasons.append("validation_failed")
        commit = None
        if validation_passed and not reasons:
            commit = commit_candidate(worktree, candidate_id, paths)
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
            commit=commit,
            rejection_reasons=tuple(reasons),
        )
    finally:
        remove_worktree(repo, worktree)


def write_cycle(state_dir: Path, cycle: CycleEvidence) -> tuple[str, Path]:
    value = cycle.to_dict()
    digest = str(value["sha256"])
    path = state_dir / "evidence" / f"g{cycle.generation:04d}-{digest[:16]}.json"
    atomic_json(path, value)
    return digest, path


def run_cycle(
    repo: Path,
    goal: GoalSpec,
    state: EvolutionState,
    state_dir: Path,
) -> tuple[EvolutionState, CycleEvidence]:
    generation = state.generation + 1
    parent_commit = state.active_commit
    candidates: list[CandidateEvidence] = []

    with tempfile.TemporaryDirectory(prefix=f"centinal26-{goal.goal_id}-") as raw_temp:
        temp_root = Path(raw_temp)
        parent_tree = temp_root / "parent"
        create_worktree(repo, parent_commit, parent_tree)
        try:
            context = build_context(parent_tree, goal)
            locked_tests = build_locked_tests(parent_tree, goal)
            _, baseline, baseline_results = evaluate(parent_tree, goal)
        finally:
            remove_worktree(repo, parent_tree)

        atomic_json(
            state_dir / "baseline-latest.json",
            {
                "commit": parent_commit,
                "goal_sha256": goal.digest(),
                "score": baseline,
                "results": baseline_results,
            },
        )

        if baseline >= 0.999999:
            state.generation = generation
            state.best_score = max(state.best_score, baseline)
            state.status = "GOAL_VALIDATED"
            return state, CycleEvidence(
                goal_id=goal.goal_id,
                goal_sha256=goal.digest(),
                generation=generation,
                parent_commit=parent_commit,
                baseline_score=baseline,
                candidates=(),
                decision="PARENT_ALREADY_VALIDATED",
                selected_candidate=None,
                selected_commit=None,
            )

        # Every candidate receives the exact promoted parent tree as context.
        parent_context_tree = temp_root / "proposal-parent"
        create_worktree(repo, parent_commit, parent_context_tree)
        try:
            for index in range(goal.candidates_per_cycle):
                candidate_id = f"g{generation:04d}-c{index + 1:02d}"
                strategy = STRATEGIES[(generation + index - 1) % len(STRATEGIES)]
                try:
                    patch = goose_patch(
                        parent_context_tree,
                        goal,
                        context,
                        locked_tests,
                        strategy,
                        candidate_id,
                    )
                    candidate = evaluate_candidate(
                        repo,
                        goal,
                        state_dir,
                        temp_root,
                        parent_commit,
                        candidate_id,
                        patch,
                    )
                except Exception as error:  # noqa: BLE001 - rejection is evidence
                    candidate = rejected_candidate(
                        candidate_id,
                        parent_commit,
                        f"agent_exception:{type(error).__name__}:{str(error)[:240]}",
                    )
                candidates.append(candidate)
        finally:
            remove_worktree(repo, parent_context_tree)

    selected = select_candidate(candidates, baseline)
    state.generation = generation
    state.best_score = max(state.best_score, baseline)
    if selected is None:
        return state, CycleEvidence(
            goal_id=goal.goal_id,
            goal_sha256=goal.digest(),
            generation=generation,
            parent_commit=parent_commit,
            baseline_score=baseline,
            candidates=tuple(candidates),
            decision="RETAIN_PARENT",
            selected_candidate=None,
            selected_commit=None,
        )

    branch = f"evolution/{goal.goal_id}/g{generation:04d}"
    git(repo, "branch", "-f", branch, selected.commit or parent_commit)
    state.active_commit = selected.commit or parent_commit
    state.active_branch = branch
    state.best_score = selected.score
    if selected.score >= 0.999999:
        state.status = "GOAL_VALIDATED"
    return state, CycleEvidence(
        goal_id=goal.goal_id,
        goal_sha256=goal.digest(),
        generation=generation,
        parent_commit=parent_commit,
        baseline_score=baseline,
        candidates=tuple(candidates),
        decision="PROMOTE_EVOLUTION_BRANCH",
        selected_candidate=selected.candidate_id,
        selected_commit=selected.commit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded patch-only open-source-agent evolution cycles."
    )
    parser.add_argument("goal", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--cycles", type=int)
    parser.add_argument(
        "--push-evolution-branch",
        action="store_true",
        help="Push only the selected evolution branch; never updates main.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git checkout: {repo}")
    require_clean_repo(repo)
    if shutil.which("goose") is None:
        raise SystemExit(
            "BLOCKED: goose CLI is not installed; no fallback agent executes implicitly"
        )

    goal = GoalSpec.load(args.goal.resolve())
    base_commit = git(repo, "rev-parse", "HEAD")
    state_root = Path(
        os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")
    ).expanduser()
    state_dir = state_root / "evolution" / goal.goal_id
    state_path = state_dir / "state.json"
    state = EvolutionState.load_or_create(
        state_path,
        goal.goal_id,
        goal.digest(),
        base_commit,
    )
    cycles = min(args.cycles or goal.max_cycles, goal.max_cycles)
    stalled = 0

    for _ in range(max(1, cycles)):
        previous = state.active_commit
        state, cycle = run_cycle(repo, goal, state, state_dir)
        digest, evidence = write_cycle(state_dir, cycle)
        state.cycles.append(digest)
        atomic_json(state_path, state.to_dict())
        print(
            json.dumps(
                {
                    "generation": state.generation,
                    "decision": cycle.decision,
                    "active_branch": state.active_branch,
                    "active_commit": state.active_commit,
                    "score": state.best_score,
                    "status": state.status,
                    "evidence": str(evidence),
                    "evidence_sha256": digest,
                },
                sort_keys=True,
            )
        )

        if state.active_commit == previous:
            stalled += 1
        else:
            stalled = 0
            if args.push_evolution_branch:
                git(
                    repo,
                    "push",
                    "--force-with-lease",
                    "origin",
                    f"{state.active_branch}:{state.active_branch}",
                    timeout=180,
                )
        if state.status == "GOAL_VALIDATED":
            break
        if stalled >= 2:
            state.status = "STALLED_REVIEW_REQUIRED"
            atomic_json(state_path, state.to_dict())
            break

    return 0 if state.status == "GOAL_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
