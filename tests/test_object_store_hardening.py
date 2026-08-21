import sqlite3

import pytest

from frost_core.object_store import AliasConflict, CanonicalObjectStore


def test_compare_and_swap_prevents_lost_update(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    first = store.put("continuity_state", {"revision": 1})
    second = store.put("continuity_state", {"revision": 2})
    stale = store.put("continuity_state", {"revision": 99})

    store.point_if_current("continuity/current", None, first, at=1.0)
    store.point_if_current("continuity/current", first, second, at=2.0)
    with pytest.raises(AliasConflict, match="expected"):
        store.point_if_current("continuity/current", first, stale, at=3.0)

    assert store.resolve("continuity/current").object_id == second
    with sqlite3.connect(store.path) as conn:
        history = conn.execute(
            "SELECT object_id FROM alias_history WHERE alias=? ORDER BY seq",
            ("continuity/current",),
        ).fetchall()
    assert [row[0] for row in history] == [first, second]


def test_compare_and_swap_requires_absence_for_initial_creation(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    first = store.put("continuity_state", {"revision": 1})
    second = store.put("continuity_state", {"revision": 2})
    store.point_if_current("continuity/current", None, first)
    with pytest.raises(AliasConflict):
        store.point_if_current("continuity/current", None, second)
    assert store.resolve("continuity/current").object_id == first


def test_compare_and_swap_rejects_unknown_target_without_history_side_effect(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    with pytest.raises(KeyError):
        store.point_if_current("continuity/current", None, "missing")
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM alias_history").fetchone()[0] == 0


def test_typed_link_validates_polymorphic_kinds(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    experiment = store.put("experiment", {"id": "exp-1"})
    run = store.put("run", {"id": "run-1"})
    store.link_typed(experiment, "experiment", "HAS_RUN", run, "run")
    with pytest.raises(ValueError, match="parent kind mismatch"):
        store.link_typed(experiment, "project", "HAS_RUN", run, "run")
    with pytest.raises(ValueError, match="child kind mismatch"):
        store.link_typed(experiment, "experiment", "HAS_RUN", run, "finding")


def test_integrity_report_is_non_destructive_and_does_not_call_history_garbage(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    historical = store.put("continuity_state", {"revision": 1})
    current = store.put("continuity_state", {"revision": 2})
    store.point("continuity/current", current)

    report = store.integrity_report()
    assert report["status"] == "PASS"
    assert report["foreign_key_violations"] == []
    assert report["objects_without_provenance"] == []
    assert report["unaliased_immutable_objects"] == 1
    assert report["garbage_collection_authorized"] is False
    assert store.get(historical).payload == {"revision": 1}


def test_integrity_report_detects_missing_provenance_without_deleting_object(tmp_path) -> None:
    store = CanonicalObjectStore(tmp_path / "store.sqlite3")
    object_id = store.put("continuity_state", {"revision": 1})
    with sqlite3.connect(store.path) as conn:
        conn.execute("DELETE FROM provenance WHERE object_id=?", (object_id,))
    report = store.integrity_report()
    assert report["status"] == "REVIEW"
    assert report["objects_without_provenance"] == [object_id]
    assert report["garbage_collection_authorized"] is False
    assert store.get(object_id).payload == {"revision": 1}
