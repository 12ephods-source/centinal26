from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from centinal26.control_plane import (
    Checkpoint,
    CircuitBreaker,
    CircuitState,
    DebtPolicy,
    DebtState,
    Phase,
    ReentrancyGuard,
    canonical_sha256,
    hourly_epoch,
)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot resolve repository identity: {result.stdout.strip()}")
    return result.stdout.strip()


def load_component_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema": "centinal26-component-state-v1",
            "component": "controlled-evolution",
            "verification_debt": 0,
            "deployment_debt": 0,
            "failure_streak": 0,
            "circuit_state": "CLOSED",
            "opened_at": None,
            "last_revalidated_at": None,
            "drift_status": "UNKNOWN",
        }
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "centinal26-component-state-v1":
        raise ValueError("component state schema mismatch")
    return value


def checkpoint_value(checkpoint: Checkpoint) -> dict[str, Any]:
    return checkpoint.to_dict()


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    state_root = Path(
        os.environ.get("CENTINAL26_HOME", "~/.local/state/centinal26")
    ).expanduser()
    control_dir = state_root / "control-plane"
    component_path = control_dir / "controlled-evolution.json"
    now = datetime.now(UTC)
    run_id = str(uuid.uuid4())

    state = load_component_state(component_path)
    debts = DebtState(
        verification_debt=int(state.get("verification_debt", 0)),
        deployment_debt=int(state.get("deployment_debt", 0)),
    )
    debt_policy = DebtPolicy(
        max_verification_debt=int(os.environ.get("CENTINAL26_MAX_VERIFICATION_DEBT", "0")),
        max_deployment_debt=int(os.environ.get("CENTINAL26_MAX_DEPLOYMENT_DEBT", "0")),
    )
    allowed, debt_reasons = debts.permits(Phase.EVOLVE, debt_policy)
    if not allowed:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_BACKPRESSURE",
                    "phase": Phase.EVOLVE.value,
                    "reasons": debt_reasons,
                },
                sort_keys=True,
            )
        )
        return 5

    breaker = CircuitBreaker(
        failure_threshold=int(os.environ.get("CENTINAL26_CIRCUIT_FAILURE_THRESHOLD", "3")),
        cooldown_seconds=int(os.environ.get("CENTINAL26_CIRCUIT_COOLDOWN_SECONDS", "3600")),
        state=CircuitState(str(state.get("circuit_state", "CLOSED"))),
        failure_count=int(state.get("failure_streak", 0)),
        opened_at=state.get("opened_at"),
    )
    if not breaker.allow(now):
        print(json.dumps({"status": "BLOCKED_CIRCUIT_OPEN"}, sort_keys=True))
        return 6

    head = git_head(root)
    immutable_inputs = {
        "repo": str(root),
        "head": head,
        "argv": arguments,
        "phase": Phase.EVOLVE.value,
    }
    lock = ReentrancyGuard(control_dir / "controlled-evolution.lock", run_id)
    try:
        lock.acquire(now)
    except RuntimeError as error:
        print(json.dumps({"status": "BLOCKED_REENTRANCY", "reason": str(error)}))
        return 7

    try:
        start = Checkpoint.create(
            run_id=run_id,
            epoch=hourly_epoch(now),
            phase=Phase.EVOLVE,
            immutable_inputs=immutable_inputs,
            result_digests=[],
            pending_obligations=[
                "fresh-evidence-before-mutation",
                "semantic-postconditions",
                "cross-epoch-promotion",
            ],
            state=state,
        )
        checkpoint_dir = control_dir / "checkpoints"
        atomic_json(checkpoint_dir / f"{run_id}-start.json", checkpoint_value(start))

        command = [
            sys.executable,
            str(root / "scripts" / "controlled_evolution_hard.py"),
            "--repo",
            str(root),
            *arguments,
        ]
        result = subprocess.run(command, cwd=root, check=False)
        end_time = datetime.now(UTC)
        if result.returncode in {0, 2}:
            # rc=2 is a normal bounded-evolution outcome: the goal is not yet
            # validated or requires review. It is not a subsystem failure.
            breaker.success()
        else:
            breaker.failure(end_time)

        state.update(
            {
                "failure_streak": breaker.failure_count,
                "circuit_state": breaker.state.value,
                "opened_at": breaker.opened_at,
            }
        )
        atomic_json(component_path, state)

        result_digest = canonical_sha256(
            {"returncode": result.returncode, "head": head, "run_id": run_id}
        )
        end = Checkpoint.create(
            run_id=run_id,
            epoch=hourly_epoch(end_time),
            phase=Phase.EVOLVE,
            immutable_inputs=immutable_inputs,
            result_digests=[result_digest],
            pending_obligations=(
                []
                if result.returncode == 0
                else ["verification-or-recovery-required-before-new-build"]
            ),
            state=state,
        )
        atomic_json(checkpoint_dir / f"{run_id}-end.json", checkpoint_value(end))
        return result.returncode
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
