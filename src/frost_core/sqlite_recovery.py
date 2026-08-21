from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteRecoveryError(RuntimeError):
    """A SQLite snapshot or restore operation failed closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, *, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise SQLiteRecoveryError(f"{label} must be a regular non-symlink file")
    return path


def _sidecars(path: Path) -> list[Path]:
    return [Path(f"{path}-wal"), Path(f"{path}-shm")]


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def verify_sqlite_database(path: str | Path) -> dict[str, Any]:
    database = _regular_file(Path(path), label="SQLite database")
    try:
        with _connect_readonly(database) as db:
            integrity = [str(row[0]) for row in db.execute("PRAGMA integrity_check").fetchall()]
            foreign_keys = [tuple(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
    except sqlite3.DatabaseError as exc:
        raise SQLiteRecoveryError("SQLite verification failed") from exc
    status = "PASS" if integrity == ["ok"] and not foreign_keys else "FAIL"
    return {
        "status": status,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "sha256": _sha256(database),
        "size_bytes": database.stat().st_size,
    }


def create_sqlite_snapshot(source: str | Path, snapshot: str | Path) -> dict[str, Any]:
    source_path = _regular_file(Path(source), label="SQLite source")
    snapshot_path = Path(snapshot)
    if snapshot_path.is_symlink():
        raise SQLiteRecoveryError("snapshot destination may not be a symlink")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = snapshot_path.with_name(f".{snapshot_path.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with _connect_readonly(source_path) as source_db, sqlite3.connect(temporary) as target_db:
            source_db.backup(target_db)
            target_db.commit()
        verification = verify_sqlite_database(temporary)
        if verification["status"] != "PASS":
            raise SQLiteRecoveryError("snapshot failed integrity verification")
        os.chmod(temporary, 0o600)
        temporary.replace(snapshot_path)
    except sqlite3.DatabaseError as exc:
        raise SQLiteRecoveryError("SQLite snapshot failed") from exc
    finally:
        temporary.unlink(missing_ok=True)
    verified = verify_sqlite_database(snapshot_path)
    return {
        "status": "SNAPSHOT_VERIFIED",
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": verified["sha256"],
        "snapshot_size_bytes": verified["size_bytes"],
    }


def restore_sqlite_snapshot(
    snapshot: str | Path,
    destination: str | Path,
    *,
    expected_current_sha256: str | None = None,
) -> dict[str, Any]:
    snapshot_path = _regular_file(Path(snapshot), label="SQLite snapshot")
    snapshot_verification = verify_sqlite_database(snapshot_path)
    if snapshot_verification["status"] != "PASS":
        raise SQLiteRecoveryError("snapshot is not eligible for restore")

    destination_path = Path(destination)
    if destination_path.is_symlink():
        raise SQLiteRecoveryError("restore destination may not be a symlink")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    active_sidecars = [path for path in _sidecars(destination_path) if path.exists()]
    if active_sidecars:
        raise SQLiteRecoveryError("restore blocked while WAL/SHM sidecars exist")

    preserved_previous: Path | None = None
    if destination_path.exists():
        current = _regular_file(destination_path, label="current SQLite destination")
        if expected_current_sha256 is None:
            raise SQLiteRecoveryError("existing destination requires expected_current_sha256")
        observed = _sha256(current)
        if observed != expected_current_sha256:
            raise SQLiteRecoveryError("current SQLite destination hash changed")
        preserved_previous = destination_path.with_name(
            f"{destination_path.name}.pre_restore.{observed[:16]}"
        )
        if preserved_previous.exists() or preserved_previous.is_symlink():
            raise SQLiteRecoveryError("pre-restore preservation target already exists")
        shutil.copy2(current, preserved_previous)
        os.chmod(preserved_previous, 0o600)

    temporary = destination_path.with_name(f".{destination_path.name}.restore.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with _connect_readonly(snapshot_path) as source_db, sqlite3.connect(temporary) as target_db:
            source_db.backup(target_db)
            target_db.commit()
        verification = verify_sqlite_database(temporary)
        if verification["status"] != "PASS":
            raise SQLiteRecoveryError("restored temporary database failed verification")
        os.chmod(temporary, 0o600)
        temporary.replace(destination_path)
    except sqlite3.DatabaseError as exc:
        raise SQLiteRecoveryError("SQLite restore failed") from exc
    finally:
        temporary.unlink(missing_ok=True)

    restored = verify_sqlite_database(destination_path)
    if restored["sha256"] != snapshot_verification["sha256"]:
        raise SQLiteRecoveryError("restored database hash does not match verified snapshot")
    return {
        "status": "RESTORE_VERIFIED",
        "destination_path": str(destination_path),
        "restored_sha256": restored["sha256"],
        "preserved_previous_path": None
        if preserved_previous is None
        else str(preserved_previous),
    }
