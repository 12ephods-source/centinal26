import sqlite3

import pytest

from frost_core.sqlite_recovery import (
    SQLiteRecoveryError,
    create_sqlite_snapshot,
    restore_sqlite_snapshot,
    verify_sqlite_database,
)


def make_database(path, value: str) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS state(value TEXT NOT NULL)")
        db.execute("DELETE FROM state")
        db.execute("INSERT INTO state(value) VALUES (?)", (value,))
        db.commit()


def read_value(path) -> str:
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT value FROM state").fetchone()
    assert row is not None
    return str(row[0])


def test_snapshot_and_restore_preserve_previous_state(tmp_path) -> None:
    database = tmp_path / "state.db"
    snapshot = tmp_path / "state.snapshot.db"
    make_database(database, "qualified")
    receipt = create_sqlite_snapshot(database, snapshot)
    assert receipt["status"] == "SNAPSHOT_VERIFIED"
    assert verify_sqlite_database(snapshot)["status"] == "PASS"

    make_database(database, "mutated")
    current_hash = verify_sqlite_database(database)["sha256"]
    restored = restore_sqlite_snapshot(
        snapshot,
        database,
        expected_current_sha256=current_hash,
    )
    assert restored["status"] == "RESTORE_VERIFIED"
    assert read_value(database) == "qualified"
    preserved = restored["preserved_previous_path"]
    assert preserved is not None
    assert read_value(preserved) == "mutated"
    assert verify_sqlite_database(preserved)["status"] == "PASS"


def test_existing_destination_requires_expected_hash(tmp_path) -> None:
    database = tmp_path / "state.db"
    snapshot = tmp_path / "state.snapshot.db"
    make_database(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    make_database(database, "changed")
    with pytest.raises(SQLiteRecoveryError, match="requires expected_current_sha256"):
        restore_sqlite_snapshot(snapshot, database)


def test_wrong_expected_hash_fails_without_mutation(tmp_path) -> None:
    database = tmp_path / "state.db"
    snapshot = tmp_path / "state.snapshot.db"
    make_database(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    make_database(database, "changed")
    before = read_value(database)
    with pytest.raises(SQLiteRecoveryError, match="hash changed"):
        restore_sqlite_snapshot(snapshot, database, expected_current_sha256="0" * 64)
    assert read_value(database) == before


def test_restore_refuses_live_wal_or_shm_sidecars(tmp_path) -> None:
    database = tmp_path / "state.db"
    snapshot = tmp_path / "state.snapshot.db"
    make_database(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    current_hash = verify_sqlite_database(database)["sha256"]
    sidecar = tmp_path / "state.db-wal"
    sidecar.write_bytes(b"active")
    with pytest.raises(SQLiteRecoveryError, match="WAL/SHM"):
        restore_sqlite_snapshot(
            snapshot,
            database,
            expected_current_sha256=current_hash,
        )
    assert read_value(database) == "qualified"


def test_corrupt_snapshot_is_not_eligible(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not sqlite")
    with pytest.raises(SQLiteRecoveryError, match="verification failed"):
        verify_sqlite_database(corrupt)


def test_snapshot_and_restore_reject_symlink_inputs(tmp_path) -> None:
    database = tmp_path / "state.db"
    snapshot = tmp_path / "state.snapshot.db"
    make_database(database, "qualified")
    create_sqlite_snapshot(database, snapshot)
    source_link = tmp_path / "source-link.db"
    snapshot_link = tmp_path / "snapshot-link.db"
    try:
        source_link.symlink_to(database)
        snapshot_link.symlink_to(snapshot)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(SQLiteRecoveryError, match="regular non-symlink"):
        create_sqlite_snapshot(source_link, tmp_path / "rejected.db")
    with pytest.raises(SQLiteRecoveryError, match="regular non-symlink"):
        restore_sqlite_snapshot(snapshot_link, tmp_path / "restored.db")
