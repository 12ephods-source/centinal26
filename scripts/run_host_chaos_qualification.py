from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Callable

from frost_core.encrypted_backup import EncryptedBackupError, encrypt_backup
from frost_core.manifest_policy import ManifestPolicyError, build_manifest
from frost_core.object_store import AliasConflict, CanonicalObjectStore
from frost_core.sqlite_recovery import (
    SQLiteRecoveryError,
    create_sqlite_snapshot,
    restore_sqlite_snapshot,
    verify_sqlite_database,
)

Scenario = Callable[[Path], None]


def _make_db(path: Path, value: str) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS state(value TEXT NOT NULL)")
        db.execute("DELETE FROM state")
        db.execute("INSERT INTO state(value) VALUES (?)", (value,))
        db.commit()


def _read_db(path: Path) -> str:
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT value FROM state").fetchone()
    if row is None:
        raise AssertionError("state row missing")
    return str(row[0])


def _expect(exc_type: type[Exception], message: str, action: Callable[[], None]) -> None:
    try:
        action()
    except exc_type as exc:
        if message not in str(exc):
            raise AssertionError(f"unexpected failure: {exc}") from exc
    else:
        raise AssertionError(f"expected {exc_type.__name__}: {message}")


def stale_alias_writer(root: Path) -> None:
    store = CanonicalObjectStore(root / "objects.db")
    first = store.put("state", {"version": 1})
    second = store.put("state", {"version": 2})
    stale = store.put("state", {"version": 3})
    store.point("release/current", first)
    store.point_if_current("release/current", first, second)
    _expect(
        AliasConflict,
        "expected",
        lambda: store.point_if_current("release/current", first, stale),
    )
    if store.resolve("release/current").object_id != second:
        raise AssertionError("stale alias writer changed canonical head")


def wrong_restore_hash(root: Path) -> None:
    database = root / "state.db"
    snapshot = root / "state.snapshot.db"
    _make_db(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    _make_db(database, "mutated")
    before = verify_sqlite_database(database)["sha256"]
    _expect(
        SQLiteRecoveryError,
        "hash changed",
        lambda: restore_sqlite_snapshot(
            snapshot,
            database,
            expected_current_sha256="0" * 64,
        ),
    )
    if verify_sqlite_database(database)["sha256"] != before or _read_db(database) != "mutated":
        raise AssertionError("failed stale-hash restore mutated destination")


def live_wal_restore(root: Path) -> None:
    database = root / "state.db"
    snapshot = root / "state.snapshot.db"
    _make_db(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    current_hash = verify_sqlite_database(database)["sha256"]
    Path(f"{database}-wal").write_bytes(b"active")
    _expect(
        SQLiteRecoveryError,
        "WAL/SHM",
        lambda: restore_sqlite_snapshot(
            snapshot,
            database,
            expected_current_sha256=current_hash,
        ),
    )
    if _read_db(database) != "qualified":
        raise AssertionError("WAL-blocked restore mutated database")


def corrupt_snapshot(root: Path) -> None:
    corrupt = root / "corrupt.db"
    corrupt.write_bytes(b"not-a-sqlite-database")
    _expect(
        SQLiteRecoveryError,
        "verification failed",
        lambda: verify_sqlite_database(corrupt),
    )


def interrupted_restore_temp(root: Path) -> None:
    database = root / "state.db"
    snapshot = root / "state.snapshot.db"
    _make_db(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    _make_db(database, "mutated")
    current_hash = verify_sqlite_database(database)["sha256"]
    temp = database.with_name(f".{database.name}.restore.tmp")
    temp.write_bytes(b"partial-interrupted-restore")
    restored = restore_sqlite_snapshot(
        snapshot,
        database,
        expected_current_sha256=current_hash,
    )
    if restored["status"] != "RESTORE_VERIFIED" or _read_db(database) != "qualified":
        raise AssertionError("interrupted restore temp was not safely recovered")
    if temp.exists():
        raise AssertionError("interrupted restore temp survived verified restore")


def manifest_symlink(root: Path) -> None:
    evidence = root / "evidence"
    evidence.mkdir()
    target = root / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    link = evidence / "linked.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        return
    _expect(
        ManifestPolicyError,
        "symlink rejected",
        lambda: build_manifest(evidence),
    )


def encrypted_backup_provider_missing(root: Path) -> None:
    source = root / "backup.zip"
    source.write_bytes(b"backup")
    output = root / "backup.age"
    recipient = "age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
    _expect(
        EncryptedBackupError,
        "plaintext fallback is forbidden",
        lambda: encrypt_backup(
            source,
            output,
            recipient=recipient,
            age_binary="definitely-not-a-real-age-provider",
        ),
    )
    if output.exists():
        raise AssertionError("missing encryption provider created output")


SCENARIOS: list[tuple[str, Scenario]] = [
    ("stale_alias_writer", stale_alias_writer),
    ("wrong_restore_hash", wrong_restore_hash),
    ("live_wal_restore", live_wal_restore),
    ("corrupt_snapshot", corrupt_snapshot),
    ("interrupted_restore_temp", interrupted_restore_temp),
    ("manifest_symlink", manifest_symlink),
    ("encrypted_backup_provider_missing", encrypted_backup_provider_missing),
]


def run() -> dict[str, object]:
    results: list[dict[str, str]] = []
    for name, scenario in SCENARIOS:
        with tempfile.TemporaryDirectory(prefix=f"frost-chaos-{name}-") as directory:
            try:
                scenario(Path(directory))
            except Exception as exc:
                results.append({"scenario": name, "status": "FAIL", "error": type(exc).__name__})
            else:
                results.append({"scenario": name, "status": "PASS", "error": ""})
    report: dict[str, object] = {
        "schema": "automation.host_chaos_qualification/v1",
        "scope": "HOST_ONLY",
        "physical_promotion_allowed": False,
        "scenarios": results,
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
