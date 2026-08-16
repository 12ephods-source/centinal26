from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from centinal26.wordbook import Attribution, EvolutionPolicy, WordbookStore, tokenize


def test_tokenize_normalizes_case_and_curly_apostrophe() -> None:
    assert tokenize("I DON’T say Basically.") == ["i", "don't", "say", "basically"]


def test_ingest_is_idempotent_by_source_identity_and_content() -> None:
    with WordbookStore() as store:
        first = store.ingest_text(
            text="Proceed. Proceed.",
            source_type="test",
            external_id="m1",
        )
        second = store.ingest_text(
            text="Proceed. Proceed.",
            source_type="test",
            external_id="m1",
        )
        assert first == second
        assert store.query("proceed").ordinary_usage == 2


def test_query_separates_attribution_classes() -> None:
    with WordbookStore() as store:
        for i, attribution in enumerate(
            (
                Attribution.USER_DIRECT,
                Attribution.META_REFERENCE,
                Attribution.QUOTED,
                Attribution.AI_GENERATED,
                Attribution.AI_ACCEPTED,
                Attribution.AI_REJECTED,
            )
        ):
            store.ingest_text(
                text="basically",
                source_type="test",
                external_id=str(i),
                attribution=attribution,
            )
        result = store.query("basically")
        assert result.authored_total == 2
        assert result.ordinary_usage == 1
        assert result.meta_reference == 1
        assert result.quoted_usage == 1
        assert result.ai_generated == 1
        assert result.ai_accepted == 1
        assert result.ai_rejected == 1


def test_phrase_counts_are_exact() -> None:
    with WordbookStore() as store:
        store.ingest_text(
            text="How can we improve this? How can we improve that?",
            source_type="test",
            external_id="p1",
        )
        assert store.query("how can we improve").ordinary_usage == 2
        assert ("how can we improve", 4, 2) in store.top_phrases(limit=100)


def test_rejections_are_first_class_and_idempotent() -> None:
    with WordbookStore() as store:
        store.record_rejection("Basically", reason="not my voice")
        store.record_rejection("basically", reason="confirmed")
        row = store.conn.execute("SELECT normalized_text, reason FROM rejections").fetchone()
        assert tuple(row) == ("basically", "confirmed")


def test_chatgpt_export_ingests_only_user_messages(tmp_path) -> None:
    export = [
        {
            "id": "c1",
            "mapping": {
                "u": {
                    "message": {
                        "id": "u1",
                        "author": {"role": "user"},
                        "create_time": 1.0,
                        "content": {"parts": ["Proceed with the test."]},
                    }
                },
                "a": {
                    "message": {
                        "id": "a1",
                        "author": {"role": "assistant"},
                        "create_time": 2.0,
                        "content": {"parts": ["Basically, done."]},
                    }
                },
            },
        }
    ]
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    with WordbookStore() as store:
        stats = store.ingest_chatgpt_export(path)
        assert stats["user_messages"] == 1
        assert stats["non_user_messages"] == 1
        assert store.query("proceed").ordinary_usage == 1
        assert store.query("basically").ordinary_usage == 0


def test_corpus_digest_is_stable_for_same_ingestion_order() -> None:
    def digest() -> str:
        with WordbookStore() as store:
            store.ingest_text(text="alpha beta", source_type="x", external_id="1")
            store.ingest_text(text="gamma", source_type="x", external_id="2")
            return store.corpus_digest()

    assert digest() == digest()


def test_evolution_is_exactly_100_generations_and_evidence_pinned() -> None:
    with WordbookStore() as store:
        store.ingest_text(
            text=("how can we improve this " * 20) + ("proceed " * 20),
            source_type="test",
            external_id="e1",
        )
        store.record_rejection("basically")
        report = store.evolve()
        assert report.generations == 100
        assert len(report.records) == 100
        assert report.promoted_generations + report.rejected_generations == 100
        assert {record.phase for record in report.records} == {
            "CORPUS_INTEGRITY",
            "TOKEN_MODEL",
            "PHRASE_DISCOVERY",
            "CONTEXT_CLASSIFICATION",
            "PERSONAL_VOCABULARY",
            "WRITING_STRUCTURE",
            "TEMPORAL_EVOLUTION",
            "DISTINCTIVENESS",
            "VOICE_RECONSTRUCTION",
            "ADVERSARIAL_VERIFICATION",
        }
        assert len({record.evidence_sha256 for record in report.records}) == 1
        stored = store.conn.execute("SELECT report_json FROM evolution_runs").fetchone()[0]
        assert json.loads(stored)["generations"] == 100


def test_evolution_refuses_other_generation_counts() -> None:
    with WordbookStore() as store:
        with pytest.raises(ValueError, match="exactly 100"):
            store.evolve(99)


def test_policy_bounds_are_enforced() -> None:
    with pytest.raises(ValueError):
        EvolutionPolicy(max_phrase_n=13).validate()


def test_empty_term_rejected() -> None:
    with WordbookStore() as store:
        with pytest.raises(ValueError):
            store.query("---")


def test_meta_discussion_does_not_become_ordinary_usage() -> None:
    with WordbookStore() as store:
        store.ingest_text(
            text="I don't say basically.",
            source_type="chat",
            external_id="meta1",
        )
        store.ingest_text(
            text="How many times have I said Basically?",
            source_type="chat",
            external_id="meta2",
        )
        result = store.query("basically")
        assert result.authored_total == 2
        assert result.ordinary_usage == 0
        assert result.meta_reference == 2


def test_quoted_word_is_not_direct_usage() -> None:
    with WordbookStore() as store:
        store.ingest_text(
            text='The draft used "basically" and I rejected it.',
            source_type="chat",
            external_id="quote1",
        )
        result = store.query("basically")
        assert result.ordinary_usage == 0
        assert result.quoted_usage == 1


def test_policy_dataclass_is_json_ready() -> None:
    assert asdict(EvolutionPolicy())["max_phrase_n"] == 8
