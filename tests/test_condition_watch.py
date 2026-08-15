import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from frost_core.condition_watch import ConditionWatchLedger

TERMINAL = {"PASS", "FAIL", "CANCELLED"}


def test_terminal_enqueues_but_is_not_acknowledged_until_delivery(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    first = ledger.observe("repo:pr:sha", "PENDING", terminal_states=TERMINAL, observed_at=1)
    terminal = ledger.observe("repo:pr:sha", "PASS", terminal_states=TERMINAL, observed_at=2)
    repeat = ledger.observe("repo:pr:sha", "PASS", terminal_states=TERMINAL, observed_at=3)

    assert not first.notify
    assert terminal.notify
    assert terminal.delivery_state == "PENDING"
    assert not repeat.notify
    state = ledger.get("repo:pr:sha")
    assert state["terminal_notified_at"] is None
    assert state["terminal_enqueued_at"] == 2
    assert state["delivery_state"] == "PENDING"


def test_crash_after_claim_is_recovered_after_lease_expiry(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    decision = ledger.observe("target", "PASS", terminal_states=TERMINAL, observed_at=10)

    first = ledger.claim_delivery("worker-a", now=11, lease_seconds=10)
    assert first is not None
    assert first.delivery_id == decision.delivery_id
    assert ledger.claim_delivery("worker-b", now=15, lease_seconds=10) is None

    second = ledger.claim_delivery("worker-b", now=22, lease_seconds=10)
    assert second is not None
    assert second.delivery_id == first.delivery_id
    assert second.attempt_count == 2
    assert ledger.acknowledge_delivery(second.delivery_id, "worker-b", delivered_at=23)
    assert not ledger.acknowledge_delivery(second.delivery_id, "worker-b", delivered_at=24)

    state = ledger.get("target")
    assert state["terminal_notified_at"] == 23
    assert state["delivery_state"] == "DELIVERED"
    assert ledger.delivery(second.delivery_id)["status"] == "DELIVERED"


def test_retryable_delivery_failure_returns_to_pending(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    decision = ledger.observe("target", "FAIL", terminal_states=TERMINAL, observed_at=1)
    claim = ledger.claim_delivery("worker-a", now=2)
    assert claim is not None

    assert ledger.fail_delivery(
        claim.delivery_id,
        "worker-a",
        "network down",
        retryable=True,
        failed_at=3,
    )
    delivery = ledger.delivery(decision.delivery_id)
    assert delivery["status"] == "PENDING"
    assert delivery["last_error"] == "network down"

    retry = ledger.claim_delivery("worker-b", now=4)
    assert retry is not None
    assert retry.attempt_count == 2


def test_terminal_delivery_failure_does_not_requeue(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    decision = ledger.observe("target", "FAIL", terminal_states=TERMINAL)
    claim = ledger.claim_delivery("worker-a")
    assert claim is not None

    ledger.fail_delivery(
        claim.delivery_id,
        "worker-a",
        "invalid destination",
        retryable=False,
    )
    assert ledger.delivery(decision.delivery_id)["status"] == "FAILED_TERMINAL"
    assert ledger.claim_delivery("worker-b") is None


def test_new_immutable_target_gets_independent_delivery(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    old = ledger.observe("repo:5:sha-old", "PASS", terminal_states=TERMINAL)
    new = ledger.observe("repo:5:sha-new", "PASS", terminal_states=TERMINAL)
    assert old.notify and new.notify
    assert old.delivery_id != new.delivery_id


def test_post_terminal_regression_does_not_reenqueue(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    first = ledger.observe("target", "PASS", terminal_states=TERMINAL)
    assert first.notify
    assert not ledger.observe("target", "PENDING", terminal_states=TERMINAL).notify
    failed = ledger.observe("target", "FAIL", terminal_states=TERMINAL)
    assert not failed.notify
    assert failed.first_terminal_state == "PASS"
    assert len(ledger.deliveries()) == 1


def test_concurrent_terminal_observations_enqueue_exactly_once(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")

    def observe_once(_):
        return ledger.observe("same-target", "PASS", terminal_states=TERMINAL).notify

    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(observe_once, range(32)))

    assert sum(decisions) == 1
    assert ledger.get("same-target")["observation_count"] == 32
    assert sum(int(row["notify"]) for row in ledger.history("same-target")) == 1
    assert len(ledger.deliveries()) == 1


def test_wrong_worker_cannot_acknowledge_or_fail_claim(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")
    ledger.observe("target", "PASS", terminal_states=TERMINAL)
    claim = ledger.claim_delivery("worker-a")
    assert claim is not None

    with pytest.raises(PermissionError):
        ledger.acknowledge_delivery(claim.delivery_id, "worker-b")
    with pytest.raises(PermissionError):
        ledger.fail_delivery(claim.delivery_id, "worker-b", "nope")


def test_legacy_v1_rows_are_migrated_to_explicit_uncertainty(tmp_path):
    path = tmp_path / "watch.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE condition_watches (
            target_key TEXT PRIMARY KEY,
            last_state TEXT NOT NULL,
            first_terminal_state TEXT,
            terminal_notified_at REAL,
            observation_count INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE condition_watch_history (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            target_key TEXT NOT NULL,
            observed_state TEXT NOT NULL,
            terminal INTEGER NOT NULL,
            notify INTEGER NOT NULL,
            observed_at REAL NOT NULL
        );
        INSERT INTO condition_watches
        VALUES ('legacy','PASS','PASS',42.0,1,1.0,42.0);
        """
    )
    db.commit()
    db.close()

    ledger = ConditionWatchLedger(path)
    state = ledger.get("legacy")
    assert state["terminal_enqueued_at"] == 42.0
    assert state["terminal_notified_at"] is None
    assert state["delivery_state"] == "LEGACY_UNCERTAIN"
    delivery = ledger.deliveries(status="LEGACY_UNCERTAIN")[0]

    ledger.resolve_legacy(delivery["delivery_id"], delivered=False, resolved_at=50)
    assert ledger.delivery(delivery["delivery_id"])["status"] == "PENDING"


def test_invalid_inputs_fail_closed(tmp_path):
    ledger = ConditionWatchLedger(tmp_path / "watch.sqlite3")

    invalid_calls = (
        lambda: ledger.observe("", "PASS", terminal_states=TERMINAL),
        lambda: ledger.observe("target", "", terminal_states=TERMINAL),
        lambda: ledger.observe("target", "PASS", terminal_states=()),
        lambda: ledger.claim_delivery("", lease_seconds=1),
        lambda: ledger.claim_delivery("worker", lease_seconds=0),
    )
    for call in invalid_calls:
        with pytest.raises(ValueError):
            call()
