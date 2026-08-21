from __future__ import annotations

import json
from pathlib import Path

from frost_core.condition_watch import ConditionWatchLedger
from frost_core.object_store import CanonicalObjectStore
from frost_core.reconciliation import (
    ControlPlaneSnapshot,
    ReconciliationLedger,
    ReconciliationState,
)


def test_legacy_control_planes_consolidate_under_one_authority(tmp_path: Path) -> None:
    store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    legacy_sources = {
        "second-brain": {"task_id": "task-42", "status": "done"},
        "aiccep": {"task_id": "task-42", "status": "complete"},
        "aaard": {"task_id": "task-42", "status": "PASS"},
        "task-hub": {"task_id": "task-42", "status": "COMPLETE"},
    }

    source_ids: dict[str, str] = {}
    for source, payload in legacy_sources.items():
        source_ids[source] = store.put(
            "legacy.control-plane-record",
            {"source": source, **payload},
            source_type="legacy-control-plane",
            source_ref=source,
            evidence_class="FIXTURE_SOURCE",
        )

    canonical_payload = {
        "task_id": "task-42",
        "status": "COMPLETE",
        "authority": "canonical-object-store",
        "source_object_ids": sorted(source_ids.values()),
    }
    canonical_id = store.put(
        "automation.task",
        canonical_payload,
        source_type="consolidation-fixture",
        source_ref="tests/test_legacy_consolidation.py",
        evidence_class="DERIVED",
    )
    for source_id in source_ids.values():
        store.link(source_id, "contributes_to", canonical_id)
    store.point("automation/task-42/current", canonical_id, at=42.0)

    assert store.resolve("automation/task-42/current").object_id == canonical_id
    assert store.resolve("automation/task-42/current").payload == canonical_payload
    assert len(store.list_kind("legacy.control-plane-record")) == 4
    for source, source_id in source_ids.items():
        assert store.get(source_id).payload["source"] == source
        provenance = store.provenance(source_id)
        assert len(provenance) == 1
        assert provenance[0]["source_ref"] == source

    ledger = ReconciliationLedger(tmp_path / "reconciliation.sqlite3")
    desired = {
        "canonical_object_id": canonical_id,
        "task_id": "task-42",
        "status": "COMPLETE",
    }
    for source, payload in legacy_sources.items():
        snapshot = ControlPlaneSnapshot(
            adapter_id=source,
            object_type="automation.task",
            object_id="task-42",
            desired=desired,
            observed={
                "task_id": "task-42",
                "status": payload["status"],
                "legacy_source": source,
            },
            immutable_evidence_identity=canonical_id,
            observed_at="2026-08-14T23:08:00Z",
        )
        pending = ledger.evaluate(snapshot)
        assert pending.state is ReconciliationState.PENDING
        assert pending.evidence_identity == canonical_id

        applied = ledger.mark_applied(snapshot, desired)
        assert applied.state is ReconciliationState.APPLIED
        mirror = ledger.last_mirror(source, "automation.task", "task-42")
        assert mirror is not None
        assert mirror["last_snapshot_identity"] == snapshot.identity
        assert json.loads(mirror["last_observed_json"]) == desired

    watch = ConditionWatchLedger(tmp_path / "condition-watch.sqlite3")
    target_key = "automation/task-42"
    decisions = [
        watch.observe(
            target_key,
            "COMPLETE",
            terminal_states={"COMPLETE"},
            observed_at=100.0 + index,
        )
        for index, _source in enumerate(legacy_sources)
    ]

    assert sum(decision.notify for decision in decisions) == 1
    deliveries = watch.deliveries()
    assert len(deliveries) == 1
    assert len(watch.history(target_key)) == 4

    claim = watch.claim_delivery(
        "fixture-worker",
        target_key=target_key,
        lease_seconds=60,
        now=200.0,
    )
    assert claim is not None
    assert watch.acknowledge_delivery(
        claim.delivery_id,
        "fixture-worker",
        attempt_count=claim.attempt_count,
        delivered_at=201.0,
    )
    assert not watch.acknowledge_delivery(
        claim.delivery_id,
        "fixture-worker",
        attempt_count=claim.attempt_count,
        delivered_at=202.0,
    )

    repeated = watch.observe(
        target_key,
        "COMPLETE",
        terminal_states={"COMPLETE"},
        observed_at=203.0,
    )
    assert repeated.notify is False
    assert watch.delivery(claim.delivery_id)["status"] == "DELIVERED"
    assert len(watch.deliveries()) == 1
    assert len(watch.history(target_key)) == 5

    reopened_store = CanonicalObjectStore(tmp_path / "objects.sqlite3")
    assert reopened_store.resolve("automation/task-42/current").object_id == canonical_id
    assert reopened_store.get(canonical_id).payload == canonical_payload
