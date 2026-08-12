from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_goal_schema_is_draft_2020_12_object() -> None:
    schema = json.loads((ROOT / "schemas/goal.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["properties"]["schema"]["const"] == "centinal26-goal-v1"
    assert schema["properties"]["goal_tests"]["items"]["pattern"] == "^tests/"


def test_reviewed_artifact_registry_is_explicit_and_empty_by_default() -> None:
    registry = json.loads(
        (ROOT / "security/reviewed_artifacts.json").read_text(encoding="utf-8")
    )
    assert registry == {
        "schema": "centinal26-reviewed-artifacts-v1",
        "artifacts": [],
    }


def test_security_policy_states_pin_is_not_benignness() -> None:
    policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    policy_flat = " ".join(policy.split())
    required = (
        "Pinning is identity, not benignness",
        "A malicious or compromised artifact can be perfectly",
        "patch-only",
        "never `main`",
        "Static analysis reduces risk but is not a proof",
    )
    for marker in required:
        assert marker in policy_flat
