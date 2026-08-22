from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

STORE_SCHEMA = "openquest.store.v1"


def default_store_root() -> Path:
    configured = os.environ.get("OPENQUEST_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "share" / "openquest" / "characters"


def character_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:20]


def save_character(payload: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    store = root or default_store_root()
    store.mkdir(parents=True, exist_ok=True)
    identifier = character_id(payload)
    record = {"schema": STORE_SCHEMA, "id": identifier, "character": payload}
    encoded = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{identifier}.", suffix=".tmp", dir=store)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, store / f"{identifier}.json")
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
    return record


def load_character(identifier: str, root: Path | None = None) -> dict[str, Any]:
    if not identifier or any(ch not in "0123456789abcdef" for ch in identifier):
        raise ValueError("Invalid character id")
    path = (root or default_store_root()) / f"{identifier}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema") != STORE_SCHEMA or record.get("id") != identifier:
        raise ValueError("Stored character record failed schema/id verification")
    character = record.get("character")
    if not isinstance(character, dict) or character_id(character) != identifier:
        raise ValueError("Stored character content hash mismatch")
    return record


def list_characters(root: Path | None = None) -> list[dict[str, Any]]:
    store = root or default_store_root()
    if not store.exists():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(store.glob("*.json")):
        try:
            record = load_character(path.stem, store)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        character = record["character"].get("character", {})
        results.append(
            {
                "id": record["id"],
                "name": character.get("name", "Unnamed"),
                "ruleset": character.get("ruleset", "unknown"),
                "level": character.get("level"),
            }
        )
    return results
