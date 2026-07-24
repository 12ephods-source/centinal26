"""
Append-only event chain with cryptographic hashes.
Each event records its own hash and the previous event's hash,
creating an immutable, verifiable timeline.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .hashing import canonical_json, sha256


def canonical_event(event: Dict[str, Any]) -> bytes:
    """Deterministic serialization for event hashing."""
    return canonical_json(event)


def hash_event(event: Dict[str, Any]) -> str:
    """Compute the SHA-256 hash of an event's canonical form."""
    return sha256(canonical_event(event))


def compute_event_hash(
    timestamp: str,
    event_type: str,
    payload: Dict[str, Any],
    previous_hash: str,
) -> str:
    """
    Compute the canonical hash for a new event.
    Excludes the event_hash field itself from the hash.
    """
    return sha256(canonical_json({
        "timestamp": timestamp,
        "event_type": event_type,
        "previous_event_hash": previous_hash,
        **payload,
    }))


def atomic_append(path: str, data: Dict[str, Any]) -> None:
    """
    Atomically append a JSON line to a file.
    Uses a temp file + rename to prevent partial writes.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".event.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as src:
                    f.write(src.read())
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def get_last_event_hash(path: str) -> str:
    """Read the hash of the most recent event from the log."""
    if not os.path.exists(path):
        return "GENESIS"
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return "GENESIS"
        return json.loads(lines[-1])["event_hash"]
    except (json.JSONDecodeError, KeyError, IndexError):
        return "GENESIS"


def log_event(
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    event_log_path: str = "events.jsonl",
) -> Dict[str, Any]:
    """
    Append a new event to the chain.
    The previous hash is read from the last line of the log.
    """
    payload = payload or {}
    previous_hash = get_last_event_hash(event_log_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    event = {
        "timestamp": timestamp,
        "event_type": event_type,
        "previous_event_hash": previous_hash,
        **payload,
    }
    event["event_hash"] = compute_event_hash(
        timestamp, event_type, payload, previous_hash
    )
    atomic_append(event_log_path, event)
    return event


def load_event_chain(path: str = "events.jsonl") -> List[Dict[str, Any]]:
    """Load the full event chain from a JSONL file."""
    if not os.path.exists(path):
        return []
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def verify_event_chain(path: str = "events.jsonl") -> Tuple[bool, str]:
    """
    Verify the integrity of the event chain.
    Returns (is_valid, reason).
    """
    events = load_event_chain(path)
    if not events:
        return True, "Empty event chain (no events yet)"

    for i, event in enumerate(events):
        # Verify self-hash
        computed = compute_event_hash(
            event["timestamp"],
            event["event_type"],
            {k: v for k, v in event.items()
             if k not in ("timestamp", "event_type", "previous_event_hash", "event_hash")},
            event["previous_event_hash"],
        )
        if computed != event["event_hash"]:
            return False, f"Event {i} self-hash mismatch"

        # Verify chain continuity
        if i == 0:
            if event["previous_event_hash"] != "GENESIS":
                return False, f"Event 0 should start with GENESIS, got {event['previous_event_hash']}"
        else:
            if event["previous_event_hash"] != events[i - 1]["event_hash"]:
                return False, f"Event {i} previous hash mismatch"

    return True, f"Chain valid ({len(events)} events)"
