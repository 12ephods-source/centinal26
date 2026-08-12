from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from dataclasses import asdict
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
    "minimal-diff: make the smallest change that satisfies the goal tests",
    "robustness: prefer explicit validation, failure handling, and maintainability",
    "alternative: solve the objective through a materially different implementation path",
    "simplify: reduce complexity while satisfying every locked evaluator",
    "adversarial: assume malformed inputs and hostile edge cases without weakening constraints",
    "performance: improve the objective while minimizing unnecessary resource use",
    "compatibility: preserve existing behavior and interfaces as aggressively as possible",
    "recovery: prioritize reversibility, diagnostics, and bounded failure behavior",
)


def run(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 180,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def git(root: Path, *args: str, timeout: int = 120) -> str:
    result = run(["git", *args], root, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout.strip()


def clean_repo(root: Path) -> None:
    status = git(root, "status", "--porcelain=v1", "--untracked-files=normal")
    if status:
        raise RuntimeError("repository working tree must be clean before controlled evolution")


def iter_context_files(root: Path, goal: GoalSpec) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for requested in goal.include_paths:
        candidate = root / requested
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(candidate)
        elif candidate.is_dir():
            for child in sorted(candidate.rglob("*")):
                if not child.is_file() or ".git" in child.parts or "__pycache__" in child.parts:
                    continue
                resolved = child.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(child)
    return paths


def build_context(root: Path, goal: GoalSpec) -> str:
    budget = goal.max_context_bytes
    blocks: list[str] = []
    used = 0
    for path in iter_context_files(root, goal):
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            if b"\x00" in raw[:4096]:
                continue
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        block = f"\n===== FILE: {relative} =====\n{text}\n"
        encoded = block.encode()
        if used + len(encoded) > budget:
            remaining = budget - used
            if remaining > 1000:
                blocks.append(encoded[:remaining].decode("utf-8", errors="ignore"))
            break
        blocks.append(block)
        used += len(encoded)
    if not blocks:
        raise RuntimeError("goal context contains no readable files")
    return "".join(blocks)


def locked_tests_context(root: Path, goal: GoalSpec) -> str:
    blocks: list[str] = []
    for relative in goal.goal_tests:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"locked goal test not found: {relative}")
        blocks.append(f"\n===== LOCKED EVALUATOR: {relative} =====\n{path.read_text(encoding='utf-8')}\n")
    return "".join(blocks)


def extract_patch(text: str) -> str:
    fenced = re.findall(r"```(?:diff|patch)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = fenced or [text]
    for candidate in candidates:
        start = candidate.find("diff --git ")
        if start >= 0:
            patch = candidate[start:].strip() + "\n"
            if "--- a/" in patch and "+++ b/" in patch:
                return patch
    raise ValueError("agent response did not contain a unified git diff")


def patch_paths(patch: str) -> list[str]:
    found: list[str] = []
    for match in re.finditer(r"^\+\+\+ b/(.+)$", patch, flags=re.MULTILINE):
        value = match.group(1).strip()
        if value != "/dev/null" and value not in found:
            found.append(value)
    return found


def validate_patch_shape(goal: GoalSpec, patch: str) -> list[str]:
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
            allowed, reason = goal.permits_changed_path(path)
        except ValueError:
            reasons.append(f"unsafe_path:{path}")
            continue
        if not allowed:
            reasons.append(f"path_denied:{path}:{reason}")
    return reasons


def goose_patch(root: Path, goal: GoalSpec, context: str, locked_tests: str, strategy: str, candidate_id: str) -> str:
    if shutil.which("goose") is None:
        raise RuntimeError("goose CLI is not installed")
    prompt = textwrap.dedent(
        f"""
        You are one mutation proposer inside a controlled software-evolution experiment.

        GOAL:
        {goal.objective}

        STRATEGY:
        {strategy}

        HARD RULES:
        - Return exactly one unified git diff beginning with `diff --git`.
        - Do not use tools, shell commands, network access, package installation, or filesystem access.
        - The repository context and locked tests below are the only evidence available.
        - Never edit tests, CI, provenance, release records, Termux control, security policy, or the evolution controller.
        - Only modify paths under: {', '.join(goal.allowed_change_prefixes)}
        - Do not weaken validation, authorization, audit, or rollback boundaries.
        - Do not add credential access, persistence, privilege escalation, remote-script execution, obfuscation, or destructive commands.
        - If the goal cannot be safely solved from the supplied context, return no patch and explain why.

        LOCKED GOAL TESTS (read-only):
        {locked_tests}

        REPOSITORY CONTEXT:
        {context}
        """
    ).strip()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "GOOSE_MODE": "chat",
        "SECURITY_PROMPT_ENABLED": "true",
        "GOOSE_PATH_ROOT": str(Path(tempfile.gettempdir()) / f"centinal26-goose-{candidate_id}"),
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
        root,
        env=env,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"goose candidate failed ({result.returncode}):\n{result.stdout[-4000:]}")
    return extract_patch(result.stdout)


def create_worktree(repo: Path, base_commit: str, path: Path) -> None:
    result = run(["git", "worktree", "add", "--detach", str(path), base_commit], repo, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"git worktree add failed:\n{result.stdout}")


def remove_worktree(repo: Path, path: Path) -> None:
    run(["git", "worktree", "remove", "--force", str(path)], repo, timeout=120)


def audit_changed_tree(repo: Path, worktree: Path, changed_paths: list[str], state_dir: Path, candidate_id: str) -> tuple[str, list[str]]:
    archive = state_dir / f"{candidate_id}-changed.zip"
    report = state_dir / f"{candidate_id}-security.json"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for relative in changed_paths:
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
        return "DENY", ["security_report_missing_or_invalid"]
    decision = str(value.get("decision", "DENY"))
    reasons = [
        f"security:{item.get('severity')}:{item.get('rule')}:{item.get('path')}:{item.get('line')}"
        for item in value.get("findings", [])
        if item.get("severity") in {"critical", "high"}
    ]
    if result.returncode != 0 and not reasons:
        reasons.append(f"security_audit_rc:{result.returncode}:{value.get('reason')}")
    return decision, reasons


def validator_commands(goal: GoalSpec) -> list[tuple[str, list[str], int]]:
    return [
        ("goal_tests", [sys.executable, "-m", "pytest", "-q", *goal.goal_tests], 300),
        ("repository_invariants", [sys.executable, "tests/validate_repository.py"], 180),
        ("compile", [sys.executable, "-m", "compileall", "-q", "src", "scripts"], 180),
    ]


def evaluate(worktree: Path, goal: GoalSpec) -> tuple[bool, float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    earned = 0.0
    weights = {"goal_tests": 0.70, "repository_invariants": 0.20, "compile": 0.10}
    passed = True
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(worktree / ".candidate-home"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONPATH": str(worktree / "src"),
        "CENTINAL26_EVOLUTION_EVALUATION": "1",
    }
    (worktree / ".candidate-home").mkdir(exist_ok=True)
    for name, command, timeout in validator_commands(goal):
        try:
            result = run(command, worktree, env=env, timeout=timeout)
            ok = result.returncode == 0
            output = result.stdout[-8000:]
        except subprocess.TimeoutExpired as exc:
            ok = False
            output = f"TIMEOUT after {timeout}s: {exc}"
        results.append({"name": name, "passed": ok, "output": output})
        if ok:
            earned += weights[name]
        else:
            passed = False
    return passed, round(earned, 6), results


def commit_candidate(worktree: Path, candidate_id: str) -> str:
    git(worktree, "add", "-A")
    staged = git(worktree, "diff", "--cached", "--name-only")
    if not staged:
        raise RuntimeError("candidate produced no staged changes")
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
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"candidate commit failed:\n{result.stdout}")
    return git(worktree, "rev-parse", "HEAD")


def baseline_score(repo: Path, goal: GoalSpec, base_commit: str, temp_root: Path) -> tuple[float, list[dict[str, Any]]]:
    worktree = temp_root / "baseline"
    create_worktree(repo, base_commit, worktree)
    try:
        _, score, results = evaluate(worktree, goal)
        return score, results
    finally:
        remove_worktree(repo, worktree)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def write_cycle(state_dir: Path, cycle: CycleEvidence) -> tuple[str, Path]:
    value = cycle.to_dict()
    digest = str(value["sha256"])
    path = state_dir / "evidence" / f"g{cycle.generation:04d}-{digest[:16]}.json"
    atomic_json(path, value)
    return digest, path


def run_cycle(repo: Path, goal: GoalSpec, state: EvolutionState, state_dir: Path) -> tuple[EvolutionState, CycleEvidence]:
    generation = state.generation + 1
    context = build_context(repo, goal)
    locked = locked_tests_context(repo, goal)
    candidates: list[CandidateEvidence] = []

    with tempfile.TemporaryDirectory(prefix=f"centinal26-{goal.goal_id}-g{generation:04d}-") as raw_temp:
        temp_root = Path(raw_temp)
        baseline, baseline_results = baseline_score(repo, goal, state.active_commit, temp_root)
        atomic_json(state_dir / "baseline-latest.json", {"commit": state.active_commit, "score": baseline, "results": baseline_results})

        for index in range(goal.candidates_per_cycle):
            candidate_id = f"g{generation:04d}-c{index + 1:02d}"
            strategy = STRATEGIES[(generation + index - 1) % len(STRATEGIES)]
            reasons: list[str] = []
            patch = ""
            changed: list[str] = []
            security_decision = "NOT_RUN"
            validation_passed = False
            validation_results: list[dict[str, Any]] = []
            score = 0.0
            commit: str | None = None

            try:
                patch = goose_patch(repo, goal, context, locked, strategy, candidate_id)
                patch_path = state_dir / "patches" / f"{candidate_id}.diff"
                patch_path.parent.mkdir(parents=True, exist_ok=True)
                patch_path.write_text(patch, encoding="utf-8")
                reasons.extend(validate_patch_shape(goal, patch))
                if reasons:
                    raise ValueError("patch shape rejected")

                worktree = temp_root / candidate_id
                create_worktree(repo, state.active_commit, worktree)
                try:
                    patch_file = state_dir / "patches" / f"{candidate_id}.diff"
                    applied = run(["git", "apply", "--whitespace=nowarn", str(patch_file)], worktree, timeout=120)
                    if applied.returncode != 0:
                        reasons.append("git_apply_failed")
                        validation_results.append({"name": "git_apply", "passed": False, "output": applied.stdout[-4000:]})
                        raise ValueError("patch could not be applied")
                    changed = [line for line in git(worktree, "diff", "--name-only").splitlines() if line]
                    for path in changed:
                        allowed, reason = goal.permits_changed_path(path)
                        if not allowed:
                            reasons.append(f"post_apply_path_denied:{path}:{reason}")
                    if reasons:
                        raise ValueError("post-apply policy rejected candidate")

                    security_decision, security_reasons = audit_changed_tree(repo, worktree, changed, state_dir, candidate_id)
                    reasons.extend(security_reasons)
                    if security_decision != "ALLOW_STATIC_ONLY":
                        if not security_reasons:
                            reasons.append(f"security_decision:{security_decision}")
                        raise ValueError("security audit rejected candidate")

                    validation_passed, score, validation_results = evaluate(worktree, goal)
                    if validation_passed:
                        commit = commit_candidate(worktree, candidate_id)
                    else:
                        reasons.append("validation_failed")
                finally:
                    remove_worktree(repo, worktree)
            except Exception as exc:  # noqa: BLE001 - candidate failures are evidence, not controller failures
                reasons.append(f"candidate_exception:{type(exc).__name__}:{str(exc)[:300]}")

            candidates.append(
                CandidateEvidence(
                    candidate_id=candidate_id,
                    agent="goose-chat-patch-only",
                    base_commit=state.active_commit,
                    patch_sha256=canonical_sha256(patch) if patch else "0" * 64,
                    changed_paths=tuple(changed),
                    security_decision=security_decision,
                    validation_passed=validation_passed,
                    validation_results=tuple(validation_results),
                    score=score,
                    commit=commit,
                    rejection_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        selected = select_candidate(candidates, baseline)
        if selected is None:
            cycle = CycleEvidence(
                goal_id=goal.goal_id,
                generation=generation,
                parent_commit=state.active_commit,
                candidates=tuple(candidates),
                decision="RETAIN_PARENT",
                selected_candidate=None,
                selected_commit=None,
            )
            state.generation = generation
            state.best_score = max(state.best_score, baseline)
            return state, cycle

        branch = f"evolution/{goal.goal_id}/g{generation:04d}"
        git(repo, "branch", "-f", branch, selected.commit or state.active_commit)
        cycle = CycleEvidence(
            goal_id=goal.goal_id,
            generation=generation,
            parent_commit=state.active_commit,
            candidates=tuple(candidates),
            decision="PROMOTE_EVOLUTION_BRANCH",
            selected_candidate=selected.candidate_id,
            selected_commit=selected.commit,
        )
        state.generation = generation
        state.active_commit = selected.commit or state.active_commit
        state.active_branch = branch
        state.best_score = selected.score
        if selected.score >= 0.999999:
            state.status = "GOAL_VALIDATED"
        return state, cycle


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded open-source-agent controlled evolution loop.")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--cycles", type=int)
    parser.add_argument(
        "--push-evolution-branch",
        action="store_true",
        help="Push only the selected evolution branch. Never updates main.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a git checkout: {repo}")
    clean_repo(repo)
    goal = GoalSpec.load(args.goal.resolve())
    if shutil.which("goose") is None:
        raise SystemExit("BLOCKED: goose CLI is not installed; no fallback agent will be executed implicitly")

    base_commit = git(repo, "rev-parse", "HEAD")
    state_root = Path(os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")).expanduser()
    state_dir = state_root / "evolution" / goal.goal_id
    state_path = state_dir / "state.json"
    state = EvolutionState.load_or_create(state_path, goal.goal_id, base_commit)
    cycles = args.cycles if args.cycles is not None else goal.max_cycles
    cycles = max(1, min(cycles, goal.max_cycles))
    stalled = 0

    print(json.dumps({"event": "evolution_start", "goal": goal.goal_id, "base": state.active_commit, "cycles": cycles}, sort_keys=True))
    for _ in range(cycles):
        previous_commit = state.active_commit
        state, cycle = run_cycle(repo, goal, state, state_dir)
        digest, evidence_path = write_cycle(state_dir, cycle)
        state.cycles.append(digest)
        atomic_json(state_path, state.to_dict())
        print(json.dumps({
            "event": "cycle_complete",
            "generation": state.generation,
            "decision": cycle.decision,
            "active_commit": state.active_commit,
            "active_branch": state.active_branch,
            "score": state.best_score,
            "status": state.status,
            "evidence": str(evidence_path),
            "evidence_sha256": digest,
        }, sort_keys=True))

        if state.active_commit == previous_commit:
            stalled += 1
        else:
            stalled = 0
            if args.push_evolution_branch:
                git(repo, "push", "--force-with-lease", "origin", f"{state.active_branch}:{state.active_branch}", timeout=180)
        if state.status == "GOAL_VALIDATED":
            break
        if stalled >= 2:
            state.status = "STALLED_REVIEW_REQUIRED"
            atomic_json(state_path, state.to_dict())
            break

    print(json.dumps({"event": "evolution_end", **state.to_dict()}, sort_keys=True))
    return 0 if state.status == "GOAL_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
