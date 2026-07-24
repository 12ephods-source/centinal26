"""
Guardian Level 1 Validation Framework

Reproducibility and audit infrastructure for computational experiments.
"""

__version__ = "1.0.0"
__level__ = 1

from .core.hashing import sha256, hash_object, canonical_json
from .core.manifest import (
    ExperimentManifest,
    EngineInfo,
    SamplingInfo,
    EnvironmentInfo,
    create_experiment_id,
)
from .core.environment import capture_environment
from .core.events import log_event, hash_event
from .core.checkpoint import (
    CheckpointEngine,
    CheckpointManager,
    recovery_resume,
    restore_rng_state,
)
from .core.executor import DeterministicExecutor
from .verifier.verify import VerificationSuite
from .verifier.policy import AttestationPolicy, determine_attestation

__all__ = [
    "__version__",
    "__level__",
    "sha256",
    "hash_object",
    "canonical_json",
    "ExperimentManifest",
    "EngineInfo",
    "SamplingInfo",
    "EnvironmentInfo",
    "create_experiment_id",
    "capture_environment",
    "log_event",
    "hash_event",
    "CheckpointEngine",
    "CheckpointManager",
    "recovery_resume",
    "restore_rng_state",
    "DeterministicExecutor",
    "VerificationSuite",
    "AttestationPolicy",
    "determine_attestation",
]
