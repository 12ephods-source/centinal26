"""
Deterministic executor with crash injection, recovery, and event logging.
"""

import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .checkpoint import CheckpointEngine, restore_rng_state
from .events import log_event


@dataclass
class ExecutionResult:
    success: bool
    final_step: int
    samples_collected: int
    results: Dict[str, Any]
    error: Optional[str] = None
    recovered: bool = False
    checkpoint_recovered_step: Optional[int] = None


class DeterministicExecutor:
    """
    Runs a computational experiment with:
    deterministic RNG (NumPy PCG64), periodic checkpointing, crash
    injection for testing, event chain logging, and recovery resumption.
    """

    def __init__(
        self,
        output_dir: str = "output",
        checkpoint_interval: int = 20,
        chunk_size: int = 5,
        seed: int = 42,
        inject_failure_at: Optional[int] = None,
        experiment_name: str = "experiment",
    ):
        self.output_dir = output_dir
        self.checkpoint_interval = checkpoint_interval
        self.chunk_size = chunk_size
        self.seed = seed
        self.inject_failure_at = inject_failure_at
        self.experiment_name = experiment_name
        self.engine: Optional[CheckpointEngine] = None
        self.rng = None
        self.step = 0
        self.samples: List[Dict[str, Any]] = []
        self.recovered = False
        self.recovered_step: Optional[int] = None

    def _setup_rng(self) -> None:
        """Initialize the deterministic RNG."""
        import numpy as np
        self.rng = np.random.default_rng(seed=self.seed)

    def _setup_engine(self) -> CheckpointEngine:
        """Initialize the checkpoint engine."""
        return CheckpointEngine(
            output_dir=self.output_dir,
            checkpoint_interval=self.checkpoint_interval,
            chunk_size=self.chunk_size,
        )

    def _chunk_results(self) -> Dict[str, Any]:
        """Package current results for checkpointing."""
        return {
            "samples": list(self.samples),
            "parameters": {
                "seed": self.seed,
                "checkpoint_interval": self.checkpoint_interval,
            },
        }

    def _summarize(self) -> Dict[str, Any]:
        """Compute summary statistics over collected samples."""
        scores = [s["score"] for s in self.samples]
        if not scores:
            return {"count": 0, "mean_score": 0.0, "min_score": 0.0, "max_score": 0.0}
        return {
            "count": len(scores),
            "mean_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
        }

    def run(
        self,
        objective_fn: Callable[[Dict[str, float]], float],
        total_samples: int = 100,
        log_path: str = "events.jsonl",
    ) -> ExecutionResult:
        """
        Execute the computational campaign.

        objective_fn  : callable that takes a parameter dict and returns a score
        total_samples : number of evaluation samples to collect
        log_path      : path to the event log
        """
        # Setup
        self._setup_rng()
        self.engine = self._setup_engine()

        # Check for recovery
        ckpt = self.engine.find_latest_checkpoint()
        if ckpt is not None:
            prior_results = self.engine.load_results_up_to(ckpt)
            restore_rng_state(self.rng, ckpt)
            self.step = ckpt.step
            self.samples = list(prior_results.get("samples", []))
            self.recovered = True
            self.recovered_step = ckpt.step
            log_event("RESUME", {
                "recovered_step": ckpt.step,
                "samples_before": len(self.samples),
            }, log_path)
            log_event(f"CHECKPOINT_{ckpt.step:05d}", {
                "step": ckpt.step,
                "samples_collected": len(self.samples),
                "recovered_checkpoint": True,
            }, log_path)

        if not self.recovered:
            log_event("JOB_CREATED", {
                "experiment": self.experiment_name,
                "seed": self.seed,
                "total_samples": total_samples,
            }, log_path)

        log_event("EVALUATION_STARTED", {
            "start_step": self.step,
            "total_samples": total_samples,
        }, log_path)

        # Main evaluation loop
        try:
            while self.step < total_samples:
                if self.inject_failure_at is not None and self.step == self.inject_failure_at:
                    raise RuntimeError(
                        f"Injected failure at step {self.step} (crash simulation)"
                    )

                x = float(self.rng.uniform(-10.0, 10.0))
                y = float(self.rng.uniform(-10.0, 10.0))
                score = float(objective_fn({"x": x, "y": y}))
                self.samples.append({"x": x, "y": y, "score": score})
                self.step += 1

                if self.step % self.checkpoint_interval == 0:
                    self.engine.write_checkpoint(
                        self.step, self.rng, self._chunk_results(),
                    )
                    log_event(f"CHECKPOINT_{self.step:05d}", {
                        "step": self.step,
                        "samples_collected": len(self.samples),
                    }, log_path)

            results = self._chunk_results()
            results["summary"] = self._summarize()

            log_event("EVALUATION_COMPLETED", {
                "final_step": self.step,
                "samples_collected": len(self.samples),
            }, log_path)
            log_event("ARTIFACT_FINALIZED", {
                "final_step": self.step,
            }, log_path)

            return ExecutionResult(
                success=True,
                final_step=self.step,
                samples_collected=len(self.samples),
                results=results,
                recovered=self.recovered,
                checkpoint_recovered_step=self.recovered_step,
            )

        except Exception as e:
            if self.step > 0:
                try:
                    self.engine.write_checkpoint(
                        self.step, self.rng, self._chunk_results(),
                        {"error": str(e)},
                    )
                    log_event(f"CHECKPOINT_{self.step:05d}", {
                        "step": self.step,
                        "samples_collected": len(self.samples),
                        "emergency": True,
                    }, log_path)
                except Exception:
                    pass

            log_event("EXECUTION_ERROR", {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "step": self.step,
            }, log_path)

            return ExecutionResult(
                success=False,
                final_step=self.step,
                samples_collected=len(self.samples),
                results=self._chunk_results(),
                error=str(e),
                recovered=self.recovered,
                checkpoint_recovered_step=self.recovered_step,
            )
