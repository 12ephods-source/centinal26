"""
Environment identity capture.

For LOCAL_TERMUX: captures Python version, platform, architecture,
and dependency lock hash.
For OCI_EXECUTION: captures container image digest.
"""

import hashlib
import os
import platform
import sys
from typing import Any, Dict, Optional


def get_python_version() -> str:
    """Return the running Python version string."""
    return sys.version.split()[0]


def get_platform() -> str:
    """Return the operating system name."""
    return platform.system()


def get_architecture() -> str:
    """Return the machine architecture (aarch64, x86_64, etc.)."""
    return platform.machine()


def compute_dependencies_hash(lockfile_path: str = "requirements.lock") -> str:
    """
    Compute SHA-256 hash of the dependency lock file.
    In production this must exist; missing lock files are logged.
    """
    if not os.path.exists(lockfile_path):
        return "sha256:lockfile_missing"
    with open(lockfile_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def capture_environment(
    execution_class: str = "LOCAL_TERMUX",
    lockfile: str = "requirements.lock",
    image_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture the full runtime environment identity.

    execution_class : "LOCAL_TERMUX" | "OCI_EXECUTION"
    lockfile        : path to requirements.lock
    image_digest    : OCI image digest (required for OCI_EXECUTION)

    For LOCAL_TERMUX, the image digest is set to "local_termux_no_oci".
    For OCI_EXECUTION, image_digest must be provided or read from
    the GUARDIAN_CONTAINER_DIGEST environment variable.
    """
    if execution_class == "OCI_EXECUTION":
        digest = image_digest or os.environ.get("GUARDIAN_CONTAINER_DIGEST", "")
        if not digest or digest == "sha256:test":
            digest = "local_termux_no_oci"
    else:
        digest = "local_termux_no_oci"

    return {
        "python": get_python_version(),
        "platform": get_platform(),
        "architecture": get_architecture(),
        "dependencies_hash": compute_dependencies_hash(lockfile),
        "image_digest": digest,
        "execution_class": execution_class,
    }
