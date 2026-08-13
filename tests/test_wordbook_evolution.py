from __future__ import annotations

from wordbook import (
    CYCLE_SPECS,
    TOTAL_CYCLES,
    CorpusSnapshot,
    EvolutionLedger,
    validate_cycle_schedule,
)


def digest(char: str) -> str:
    return char * 64


def baseline() -> CorpusSnapshot:
    return CorpusSnapshot(
        generation=0,
        corpus_sha256=digest("a"),
        parent_sha256=None,
        encounter_count=100,
        source_count=10,
        canonical_entry_count=80,
    )


def test_schedule_is_exactly_100_distinct_successive_objectives() -> None:
    validate_cycle_schedule()
    assert TOTAL_CYCLES == 100
    assert len(CYCLE_SPECS) == 100
    assert [spec.cycle for spec in CYCLE_SPECS] == list(range(1, 101))
    assert len({spec.objective for spec in CYCLE_SPECS}) == 100
    stages = [spec.stage for spec in CYCLE_SPECS]
    assert len(set(stages)) == 10
    assert all(stages.count(stage) == 10 for stage in set(stages))


def test_cycle_must_consume_immediately_previous_accumulated_corpus() -> None:
    ledger = EvolutionLedger(baseline_sha256=digest("a"), active_snapshot=baseline())
    spec = CYCLE_SPECS[0]
    output = CorpusSnapshot(
        generation=1,
        corpus_sha256=digest("b"),
        parent_sha256=digest("a"),
        encounter_count=101,
        source_count=10,
        canonical_entry_count=81,
    )
    metrics = {key: 1.0 for key in spec.metric_keys}
    evidence = ledger.advance(spec, output, metrics)
    assert evidence.accepted is True
    assert ledger.active_snapshot == output
    assert ledger.next_cycle == 2


def test_skipping_a_cycle_is_rejected_and_requires_review() -> None:
    ledger = EvolutionLedger(baseline_sha256=digest("a"), active_snapshot=baseline())
    spec = CYCLE_SPECS[1]
    output = CorpusSnapshot(
        generation=2,
        corpus_sha256=digest("b"),
        parent_sha256=digest("a"),
        encounter_count=100,
        source_count=10,
        canonical_entry_count=80,
    )
    metrics = {key: 1.0 for key in spec.metric_keys}
    evidence = ledger.advance(spec, output, metrics)
    assert evidence.accepted is False
    assert ledger.status == "REVIEW_REQUIRED"
    assert any(reason.startswith("out_of_order") for reason in evidence.reasons)


def test_resetting_to_baseline_in_later_cycle_is_rejected() -> None:
    ledger = EvolutionLedger(baseline_sha256=digest("a"), active_snapshot=baseline())
    first = CYCLE_SPECS[0]
    generation_one = CorpusSnapshot(
        generation=1,
        corpus_sha256=digest("b"),
        parent_sha256=digest("a"),
        encounter_count=100,
        source_count=10,
        canonical_entry_count=80,
    )
    ledger.advance(first, generation_one, {key: 1.0 for key in first.metric_keys})
    second = CYCLE_SPECS[1]
    reset_output = CorpusSnapshot(
        generation=2,
        corpus_sha256=digest("c"),
        parent_sha256=digest("a"),
        encounter_count=100,
        source_count=10,
        canonical_entry_count=80,
    )
    evidence = ledger.advance(
        second,
        reset_output,
        {key: 1.0 for key in second.metric_keys},
    )
    assert evidence.accepted is False
    assert "output_parent_does_not_match_active_corpus" in evidence.reasons


def test_encounter_or_source_history_cannot_regress() -> None:
    ledger = EvolutionLedger(baseline_sha256=digest("a"), active_snapshot=baseline())
    spec = CYCLE_SPECS[0]
    output = CorpusSnapshot(
        generation=1,
        corpus_sha256=digest("b"),
        parent_sha256=digest("a"),
        encounter_count=99,
        source_count=9,
        canonical_entry_count=50,
    )
    evidence = ledger.advance(spec, output, {key: 1.0 for key in spec.metric_keys})
    assert evidence.accepted is False
    assert "encounter_history_regressed" in evidence.reasons
    assert "source_history_regressed" in evidence.reasons


def test_missing_cycle_metrics_blocks_advancement() -> None:
    ledger = EvolutionLedger(baseline_sha256=digest("a"), active_snapshot=baseline())
    spec = CYCLE_SPECS[0]
    output = CorpusSnapshot(
        generation=1,
        corpus_sha256=digest("b"),
        parent_sha256=digest("a"),
        encounter_count=100,
        source_count=10,
        canonical_entry_count=80,
    )
    evidence = ledger.advance(spec, output, {})
    assert evidence.accepted is False
    assert any(reason.startswith("missing_metrics") for reason in evidence.reasons)


def test_cycle_100_marks_lineage_complete() -> None:
    snapshot = CorpusSnapshot(
        generation=99,
        corpus_sha256=digest("a"),
        parent_sha256=digest("b"),
        encounter_count=1000,
        source_count=100,
        canonical_entry_count=600,
    )
    ledger = EvolutionLedger(
        baseline_sha256=digest("0"),
        active_snapshot=snapshot,
        next_cycle=100,
        evidence_chain=[digest("e")],
    )
    spec = CYCLE_SPECS[99]
    output = CorpusSnapshot(
        generation=100,
        corpus_sha256=digest("f"),
        parent_sha256=digest("a"),
        encounter_count=1000,
        source_count=100,
        canonical_entry_count=600,
    )
    evidence = ledger.advance(spec, output, {key: 1.0 for key in spec.metric_keys})
    assert evidence.accepted is True
    assert ledger.next_cycle == 101
    assert ledger.status == "COMPLETE_100"
