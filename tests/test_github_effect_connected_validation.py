import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "provenance" / "github_actions_effect_provider_connected_validation.json"
sys.path.insert(0, str(ROOT / "src"))

from frost_core.federation import AdapterStatus, default_federation_catalog


def test_github_effect_capability_is_narrowly_connected_validated() -> None:
    catalog = default_federation_catalog()
    github = catalog.get("github-actions")

    assert github.status is AdapterStatus.CONNECTED_VALIDATED
    assert "github.runtime.qualification_marker.put" in github.operations
    assert "*" not in github.operations
    assert not any("shell" == operation or operation.endswith(".shell") for operation in github.operations)


def test_connected_validation_requires_independent_git_verifier() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["adapter_status"] == "CONNECTED_VALIDATED"
    assert evidence["capability"] == "github.runtime.qualification_marker.put"
    assert evidence["authority"] == {
        "guardian_policy": "github-actions-qualification-marker/v1",
        "caller_supplied_path": False,
        "shell": False,
        "network_target_selection": False,
        "arbitrary_github_write": False,
    }

    initial = evidence["initial_effect"]
    verified = evidence["independent_connected_validation"]
    assert initial["qualification_basis"] is False
    assert verified["verifier_id"] == "github-actions-effect-independent-git/v2"
    assert verified["independent"] is True
    assert verified["verification_decision"] == "POSTCONDITION_VERIFIED"
    assert verified["idempotent_replay"] is True
    assert verified["same_effect_commit_as_initial"] is True
    assert verified["effect_commit"] == initial["effect_commit"]
    assert verified["marker_sha256"] == initial["marker_sha256"]
    assert verified["provider_idempotency_key"] == initial["provider_idempotency_key"]
    assert all(verified["postconditions"].values())


def test_denial_is_verified_against_remote_marker_absence() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    denial = evidence["independent_guardian_denial"]

    assert denial["verifier_id"] == "github-actions-effect-independent-git/v2"
    assert denial["verification_decision"] == "DENIAL_VERIFIED"
    assert len(denial["remote_ref_sha"]) == 40
    assert denial["provider_execution_absent"] is True
    assert denial["derived_marker_absent_at_remote_ref"] is True
    assert denial["intent_absent"] is True


def test_termux_remains_host_validated_until_physical_evidence_exists() -> None:
    catalog = default_federation_catalog()
    termux = catalog.get("termux-local")
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    assert termux.status is AdapterStatus.HOST_VALIDATED
    assert evidence["limitations"]["physical_android_validated"] is False
    assert evidence["limitations"]["generic_capability_factory_promoted"] is False
