"""
Canonical serialization and SHA-256 hashing.
Level 1 trust boundary: deterministic byte representation.
"""

import hashlib
import json
from typing import Any, Dict


def canonical_json(data: Dict[str, Any]) -> bytes:
    """
    Deterministic JSON serialization for hashing:
    sorted keys, UTF-8 encoding, no extra whitespace, consistent separators.
    """
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    """Return the hex digest of a SHA-256 hash."""
    return hashlib.sha256(data).hexdigest()


def hash_object(obj: Dict[str, Any]) -> str:
    """Hash a dictionary using canonical JSON serialization."""
    return sha256(canonical_json(obj))


def hash_file(path: str, chunk_size: int = 8192) -> str:
    """
    Compute SHA-256 of a file by streaming chunks.
    Used for checkpoint and artifact verification.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
