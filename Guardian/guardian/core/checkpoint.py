"""
Checkpoint engine: atomic writes, deterministic RNG state,
crash detection, and recovery resumption.
"""

import glob
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .hashing import hash_file


@dataclass
class Checkpoint:
    step: int
    checkpoint_id: str
    rng_state: Dict[str, Any]     # NumPy bit_generator.state
    chunk_path: str
    chunk_hash: str                # SHA-256 of the chunk file
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "checkpoint_id": self.checkpoint_id,
            "rng_state": self.rng_state,
            "chunk_path": self.chunk_path,
            "chunk_hash": self.chunk_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def verify(self, base_dir: str = ".") -> bool:
        """Verify the chunk file matches the stored hash."""
        full_path = os.path.join(base_dir, self.chunk_path)
        if not os.path.exists(full_path):
            return False
        return hash_file(full_path) == self.chunk_hash


class CheckpointEngine:
    """Manages atomic checkpoint writes with deterministic RNG state."""

    def __init__(
        self,
        output_dir: str = "output",
        checkpoint_interval: int = 20,
        chunk_size: int = 5,
    ):
        self.output_dir = output_dir
        self.checkpoint_interval = checkpoint_interval
        self.chunk_size = chunk_size
        self.step = 0
        self.checkpoints: List[Checkpoint] = []
        os.makedirs(output_dir, exist_ok=True)

    def _chunk_filename(self, step: int) -> str:
        return os.path.join(self.output_dir, f"chunk_{step:05d}.json")

    def _checkpoint_filename(self, step: int) -> str:
        return os.path.join(self.output_dir, f"checkpoint_{step:05d}.json")

    def write_chunk(self, step: int, data: Dict[str, Any]) -> str:
        """Write a single chunk to disk with atomic rename."""
        path = self._chunk_filename(step)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return path

    def write_checkpoint(
        self,
        step: int,
        rng,
        results_so_far: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """
        Atomically write a checkpoint:
        write the chunk data, store the RNG state, compute the chunk
        hash, and write the checkpoint metadata.
        """
        # Write chunk
        chunk_data = {
            "step": step,
            "results": results_so_far,
        }
        chunk_path = self.write_chunk(step, chunk_data)
        chunk_hash = hash_file(chunk_path)

        # Store RNG state
        rng_state = rng.bit_generator.state

        checkpoint_id = f"checkpoint_{step:05d}"
        checkpoint = Checkpoint(
            step=step,
            checkpoint_id=checkpoint_id,
            rng_state=rng_state,
            chunk_path=os.path.basename(chunk_path),
            chunk_hash=chunk_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        # Atomic checkpoint metadata write
        ckpt_path = self._checkpoint_filename(step)
        tmp = ckpt_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ckpt_path)

        self.checkpoints.append(checkpoint)
        self.step = step
        return checkpoint

    def find_latest_checkpoint(self, output_dir: Optional[str] = None) -> Optional[Checkpoint]:
        """Discover the most recent valid checkpoint."""
        output_dir = output_dir or self.output_dir
        pattern = os.path.join(output_dir, "checkpoint_*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            return None

        # Check each checkpoint from newest to oldest
        for path in reversed(files):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                ckpt = Checkpoint(**data)
                if ckpt.verify(output_dir):
                    return ckpt
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                continue
        return None

    def load_results_up_to(self, checkpoint: Checkpoint, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Load all chunk data up to and including the given checkpoint step."""
        output_dir = output_dir or self.output_dir
        results: Dict[str, Any] = {"samples": [], "parameters": {}}
        pattern = os.path.join(output_dir, "chunk_*.json")
        for chunk_path in sorted(glob.glob(pattern)):
            with open(chunk_path, "r") as f:
                chunk = json.load(f)
            if chunk.get("step", -1) > checkpoint.step:
                continue
            chunk_results = chunk.get("results", {})
            if "samples" in chunk_results:
                results["samples"] = chunk_results["samples"]
            if "parameters" in chunk_results:
                results["parameters"] = chunk_results["parameters"]
        return results

    def discover_checkpoints(self, output_dir: Optional[str] = None) -> List[Checkpoint]:
        """Find all valid checkpoints in the output directory."""
        output_dir = output_dir or self.output_dir
        pattern = os.path.join(output_dir, "checkpoint_*.json")
        files = sorted(glob.glob(pattern))
        valid = []
        for path in files:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                ckpt = Checkpoint(**data)
                if ckpt.verify(output_dir):
                    valid.append(ckpt)
            except Exception:
                continue
        return valid


def restore_rng_state(rng, checkpoint: Checkpoint) -> None:
    """Restore the NumPy random state from a checkpoint."""
    rng.bit_generator.state = checkpoint.rng_state


class CheckpointManager(CheckpointEngine):
    """Alias for discoverability and recovery workflows."""
    pass


def recovery_resume(
    output_dir: str = "output",
    rng=None,
) -> Tuple[Optional[Checkpoint], Optional[Dict[str, Any]]]:
    """
    Detect a valid checkpoint and restore the execution state.
    Returns (checkpoint, results_so_far) or (None, None) if no recovery needed.
    """
    manager = CheckpointManager(output_dir)
    ckpt = manager.find_latest_checkpoint()
    if ckpt is None:
        return None, None

    results = manager.load_results_up_to(ckpt)
    if rng is not None:
        restore_rng_state(rng, ckpt)

    return ckpt, results
