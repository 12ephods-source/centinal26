"""
Experiment manifest: immutable identity contract.
Created before execution; locked and never modified afterward.
"""

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple

from .hashing import hash_object, sha256


@dataclass
class EngineInfo:
    name: str
    version: str
    code_id: str          # Git commit hash
    code_hash: str        # SHA-256 of the source file(s)


@dataclass
class SamplingInfo:
    method: str           # e.g., "numpy_random_pcg"
    samples: int
    seed: int             # User-visible seed for reproducibility
    sampler_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvironmentInfo:
    python: str           # e.g., "3.13.0"
    dependencies_hash: str
    image_digest: str     # OCI digest or "local_termux_no_oci"
    platform: str         # e.g., "Linux"
    architecture: str     # e.g., "x86_64"
    execution_class: str  # "LOCAL_TERMUX" or "OCI_EXECUTION"


@dataclass
class RecoveryConfig:
    checkpoint_interval: int = 20     # checkpoint every N samples
    chunk_size: int = 5               # chunk size for restart efficiency
    output_dir: str = "output"


@dataclass
class ExperimentManifest:
    manifest_version: str = "1.0"
    experiment_id: str = ""
    engine: EngineInfo = field(default_factory=lambda: EngineInfo(
        name="GuardianFToE", version="1.0.0", code_id="", code_hash=""
    ))
    parameters: Dict[str, Any] = field(default_factory=dict)
    sampling: SamplingInfo = field(default_factory=lambda: SamplingInfo(
        method="unknown", samples=0, seed=0
    ))
    environment: EnvironmentInfo = field(default_factory=lambda: EnvironmentInfo(
        python="", dependencies_hash="", image_digest="",
        platform="", architecture="", execution_class="LOCAL_TERMUX"
    ))
    criteria: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "experiment_id": self.experiment_id,
            "engine": asdict(self.engine),
            "parameters": self.parameters,
            "sampling": asdict(self.sampling),
            "environment": asdict(self.environment),
            "criteria": self.criteria,
            "outputs": self.outputs,
            "verification": self.verification,
            "recovery": asdict(self.recovery),
        }

    def hash(self) -> str:
        """Compute the manifest's canonical identity hash."""
        return hash_object(self.to_dict())

    def save(self, path: str) -> None:
        """Write the manifest to disk as canonical JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "ExperimentManifest":
        """Load a manifest from disk."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            manifest_version=data.get("manifest_version", "1.0"),
            experiment_id=data.get("experiment_id", ""),
            engine=EngineInfo(**data.get("engine", {})),
            parameters=data.get("parameters", {}),
            sampling=SamplingInfo(**data.get("sampling", {})),
            environment=EnvironmentInfo(**data.get("environment", {})),
            criteria=data.get("criteria", {}),
            outputs=data.get("outputs", {}),
            verification=data.get("verification", {}),
            recovery=RecoveryConfig(**data.get("recovery", {})),
        )


def create_experiment_id(
    parameters: Dict[str, Any],
    code_id: str,
    env_id: str,
) -> str:
    """Derive the experiment ID from configuration, code, and environment."""
    return hash_object({
        "parameters": parameters,
        "code_id": code_id,
        "env_id": env_id,
    })


def get_code_identity(repo_path: str = ".") -> Tuple[str, str]:
    """
    Return (git_commit_hash, source_hash) for the current repository state.
    If not a git repo, returns ("not_a_git_repo", "").
    """
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        commit = cp.stdout.strip()

        # Hash all .py files in the guardian package
        py_files = []
        for root, _, files in os.walk(os.path.join(repo_path, "guardian")):
            py_files.extend(
                os.path.join(root, f)
                for f in files if f.endswith(".py")
            )
        py_files.sort()
        hasher = sha256(b"")
        for pf in py_files:
            with open(pf, "rb") as f:
                hasher = sha256(hasher.encode() + f.read())
        source_hash = hasher
        return commit, source_hash
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "not_a_git_repo", ""
