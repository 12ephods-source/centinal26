from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from frost_core.intelligence_controller import IntelligenceController


def at(hour: int, minute: int = 0, *, day: int = 14) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=UTC)


def test_immediate_change_dispatch_and_deduplication(tmp_path: Path) -> None:
    ctl = IntelligenceController(tmp_path / "intelligence.sqlite3")
    try:
        first = ctl.observe(
            source_kind="WORKER",
            source_key="android-termux",
            change_type="CRITICAL_CONTRADICTION",
            severity="HIGH",
            evidence={"platform": "chatgpt/session", "android_termux_worker_seen": False},
            contradiction={"expected": "android/termux", "observed": "chatgpt/session"},
            now=at(5),
        )
        assert first is not None
        assert first["dispatch_class"] == "IMMEDIATE"
        assert ctl.observe(
            source_kind="WORKER",
            source_key="android-termux",
            change_type="CRITICAL_CONTRADICTION",
            severity="HIGH",
            evidence={"platform": "chatgpt/session", "android_termux_worker_seen": False},
            contradiction={"expected": "android/termux", "observed": "chatgpt/session"},
            now=at(5, 1),
        ) is None
        second = ctl.observe(
            source_kind="WORKER",
            source_key="android-termux",
            change_type="STATE_CHANGE",
            severity="HIGH",
            evidence={"platform": "android/termux", "android_termux_worker_seen": True},
            now=at(5, 2),
        )
        assert second is not None
        assert ctl.verify_event_chain()
        due = ctl.due_work(at(5, 3))
        assert [item["dispatch_class"] for item in due] == ["IMMEDIATE", "IMMEDIATE"]
    finally:
        ctl.close()


def test_weekly_conversation_priority_and_no_repeat(tmp_path: Path) -> None:
    ctl = IntelligenceController(tmp_path / "intelligence.sqlite3")
    try:
        ctl.register_conversation("p2", "P2", review_class="P2", strategic_value=1.0)
        ctl.register_conversation("p1-low", "P1 low", review_class="P1", strategic_value=0.5)
        ctl.register_conversation("p1-high", "P1 high", review_class="P1", strategic_value=0.9)
        ctl.register_conversation("p0", "P0", review_class="P0", strategic_value=0.1)
        now = at(12)
        assert ctl.next_conversation(now)["conversation_key"] == "p0"
        ctl.record_review(
            "p0",
            unique_signal="signal",
            contradiction="",
            open_loop="",
            decision="continue",
            implementation_state="TESTED",
            architectural_implication="close P0 first",
            confidence=0.9,
            source_basis="DIRECT_CONVERSATION",
            now=now,
        )
        assert ctl.next_conversation(now)["conversation_key"] == "p1-high"
        coverage = ctl.coverage(now)
        assert coverage["reviewed_count"] == 1
        assert coverage["remaining_by_class"]["P0"] == 0
        assert coverage["remaining_count"] == 3
    finally:
        ctl.close()


def test_scheduled_work_is_exactly_once_per_window(tmp_path: Path) -> None:
    ctl = IntelligenceController(tmp_path / "intelligence.sqlite3")
    try:
        ctl.register_conversation("c1", "Conversation", review_class="P1", strategic_value=0.9)
        now = at(6, 7)
        first = ctl.ensure_scheduled_work(now)
        second = ctl.ensure_scheduled_work(now + timedelta(minutes=1))
        assert len(first) == 6
        assert second == []
        later = ctl.ensure_scheduled_work(now + timedelta(minutes=10))
        assert later == ["scheduled:ORDINARY_REVIEW:2026-08-14T00:10"]
        due = ctl.due_work(now + timedelta(minutes=10))
        kinds = {item["kind"] for item in due}
        assert {
            "ORDINARY_REVIEW",
            "DEEP_SYNTHESIS",
            "PORTFOLIO_REVIEW",
            "SCIENTIFIC_COMPATIBILITY",
            "FULL_CORPUS_AUDIT",
            "ARCHITECTURE_REVIEW",
        } <= kinds
    finally:
        ctl.close()


def test_claim_lease_recovery_and_event_processing(tmp_path: Path) -> None:
    ctl = IntelligenceController(tmp_path / "intelligence.sqlite3")
    try:
        event = ctl.observe(
            source_kind="JOB",
            source_key="j1",
            change_type="NEW_EVIDENCE",
            severity="MEDIUM",
            evidence={"status": "completed", "result_sha256": "abc"},
            now=at(7),
        )
        assert event is not None
        work_key = f"event:{event['event_key']}"
        claim = ctl.claim_work(work_key, claimer="worker-a", lease_seconds=5, now=at(7))
        assert claim is not None
        assert ctl.claim_work(work_key, claimer="worker-b", now=at(7, 0)) is None
        recovered = ctl.claim_work(
            work_key,
            claimer="worker-b",
            now=at(7) + timedelta(seconds=6),
        )
        assert recovered is not None
        assert recovered["claimed_by"] == "worker-b"
        ctl.complete_work(work_key, result={"status": "processed"}, now=at(7, 1))
        row = ctl.db.execute(
            "SELECT status FROM event_processing WHERE event_key=?", (event["event_key"],)
        ).fetchone()
        assert row["status"] == "PROCESSED"
        ctl.complete_work(work_key, result={"status": "processed"}, now=at(7, 2))
    finally:
        ctl.close()


def test_change_event_ledger_is_append_only(tmp_path: Path) -> None:
    ctl = IntelligenceController(tmp_path / "intelligence.sqlite3")
    try:
        ctl.observe(
            source_kind="VALIDATION",
            source_key="v1",
            change_type="STATE_CHANGE",
            severity="LOW",
            evidence={"state": "PASS"},
            now=at(8),
        )
        with pytest.raises(sqlite3.IntegrityError):
            ctl.db.execute("UPDATE change_events SET severity='CRITICAL'")
        ctl.db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            ctl.db.execute("DELETE FROM change_events")
        ctl.db.rollback()
        assert ctl.verify_event_chain()
    finally:
        ctl.close()
