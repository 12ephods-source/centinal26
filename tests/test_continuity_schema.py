from __future__ import annotations

import json
from pathlib import Path

from frost_core.continuity_schema import (
    generate_json_schema,
    generate_markdown,
    load_source,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "automation" / "continuity_schema_source.json"
SCHEMA = ROOT / "schemas" / "continuity_migration_proposal.schema.json"
DOC = ROOT / "docs" / "generated" / "CONTINUITY_SCHEMA.md"


def test_generated_schema_matches_single_governed_source() -> None:
    source = load_source(SOURCE)
    committed = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert committed == generate_json_schema(source)


def test_generated_documentation_matches_single_governed_source() -> None:
    source = load_source(SOURCE)
    assert DOC.read_text(encoding="utf-8") == generate_markdown(source)


def test_source_entity_types_are_unique_and_cover_second_brain_domain() -> None:
    source = load_source(SOURCE)
    entity_types = set(source["entity_types"])
    assert {
        "project",
        "theory_claim",
        "experiment",
        "run",
        "finding",
        "evidence",
        "decision",
        "environment",
        "artifact_metadata",
        "code_module",
        "test_plan",
        "security_case",
        "knowledge_task",
        "ai_session",
        "knowledge_revision",
    } <= entity_types


def test_authority_source_cannot_grant_execution_or_promotion() -> None:
    source = load_source(SOURCE)
    invariants = source["authority_invariants"]
    assert invariants["status"] == "PROPOSAL_ONLY"
    assert invariants["machine_continuation"] == "automation/PROJECT_STATE.json"
    assert invariants["execution_authority"] is False
    assert invariants["automatic_epistemic_promotion"] is False
    assert invariants["automatic_contradiction_resolution"] is False
    assert invariants["alias_or_current_pointer_update"] is False
