#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any

from centinal26.evolution import GoalSpec, canonical_sha256


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _safe_candidate_id(value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    if not rendered:
        raise ValueError("candidate id is empty after normalization")
    return rendered[:120]


def _goal_path(repo: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()
    goals_root = (repo / "goals").resolve()
    try:
        path.relative_to(goals_root)
    except ValueError as error:
        raise ValueError("goal must be stored under repository goals/") from error
    if not path.is_file():
        raise ValueError(f"goal does not exist: {path}")
    return path


def _write_blocked(
    output: Path,
    *,
    status: str,
    reason: str,
    base_commit: str | None = None,
) -> None:
    value: dict[str, Any] = {
        "schema": "centinal26-evolution-candidate-evidence-v1",
        "status": status,
        "reason": reason,
    }
    if base_commit:
        value["base_commit"] = base_commit
    value["sha256"] = canonical_sha256(value)
    _atomic_json(output, value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one pre-generated evolution patch against a locked goal "
            "in the hard sandbox."
        )
    )
    parser.add_argument("goal")
    parser.add_argument("patch", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base-commit")
    parser.add_argument("--candidate-id", default="external-candidate")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evolution-candidate-evidence.json"),
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    output = args.output.resolve()
    if not (repo / ".git").exists():
        _write_blocked(
            output,
            status="BLOCKED_REPOSITORY",
            reason=f"not a git checkout: {repo}",
        )
        return 5

    hard = _load_module(
        "centinal26_controlled_evolution_hard_external",
        repo / "scripts" / "controlled_evolution_hard.py",
    )
    legacy = hard._load_legacy()
    base_commit = legacy.git(repo, "rev-parse", "HEAD")
    expected_base = args.base_commit or base_commit
    if base_commit != expected_base:
        _write_blocked(
            output,
            status="BLOCKED_BASE_MISMATCH",
            reason=f"checked out base {base_commit} != expected {expected_base}",
            base_commit=base_commit,
        )
        return 5
    if legacy.git(repo, "status", "--porcelain=v1"):
        _write_blocked(
            output,
            status="BLOCKED_DIRTY_BASE",
            reason="trusted base checkout must be clean",
            base_commit=base_commit,
        )
        return 5

    goal = GoalSpec.load(_goal_path(repo, args.goal))
    patch_path = args.patch.resolve()
    if not patch_path.is_file():
        _write_blocked(
            output,
            status="BLOCKED_PATCH",
            reason=f"patch does not exist: {patch_path}",
            base_commit=base_commit,
        )
        return 5
    patch = patch_path.read_text(encoding="utf-8")
    candidate_id = _safe_candidate_id(args.candidate_id)

    try:
        with tempfile.TemporaryDirectory(
            prefix="centinal26-external-evolution-"
        ) as raw_temp:
            temp_root = Path(raw_temp)
            state_dir = temp_root / "state"
            baseline_tree = temp_root / "baseline"
            legacy.create_worktree(repo, base_commit, baseline_tree)
            try:
                baseline_passed, baseline_score, baseline_results = (
                    hard._hard_evaluate(legacy, baseline_tree, goal)
                )
            finally:
                legacy.remove_worktree(repo, baseline_tree)

            candidate = hard._hard_evaluate_candidate(
                legacy,
                repo,
                goal,
                state_dir,
                temp_root,
                base_commit,
                candidate_id,
                patch,
            )
    except hard.EvolutionSandboxBlocked as error:
        _write_blocked(
            output,
            status="BLOCKED_HARD_SANDBOX",
            reason=str(error),
            base_commit=base_commit,
        )
        return 4
    finally:
        try:
            legacy.git(repo, "worktree", "prune")
        except Exception:
            pass

    improves = bool(candidate.validation_passed and candidate.score > baseline_score)
    if improves:
        decision = "VALIDATED_IMPROVEMENT"
        exit_code = 0
    elif candidate.validation_passed:
        decision = "VALIDATED_NO_IMPROVEMENT"
        exit_code = 2
    else:
        decision = "REJECTED"
        exit_code = 3

    value = {
        "schema": "centinal26-evolution-candidate-evidence-v1",
        "status": decision,
        "goal_id": goal.goal_id,
        "goal_sha256": goal.digest(),
        "base_commit": base_commit,
        "candidate_id": candidate_id,
        "patch_sha256": canonical_sha256(patch),
        "baseline_passed": baseline_passed,
        "baseline_score": baseline_score,
        "baseline_results": baseline_results,
        "candidate": asdict(candidate),
        "improves_baseline": improves,
    }
    value["sha256"] = canonical_sha256(value)
    _atomic_json(output, value)
    print(json.dumps(value, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
