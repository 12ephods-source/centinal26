import pytest

from frost_core.defensive_repair_adapter import (
    AUTHORIZED_SCOPE,
    DefensiveRepairAdapter,
    DefensiveRepairOperation,
    DefensiveRepairRequest,
)
from frost_core.defensive_repair_benchmark import FIXTURE_ID


def test_all_operations_fail_closed_for_wrong_fixture() -> None:
    adapter = DefensiveRepairAdapter()
    for operation in DefensiveRepairOperation:
        with pytest.raises(PermissionError, match="pinned repository-owned fixture"):
            adapter.invoke(
                DefensiveRepairRequest(
                    operation,
                    fixture_id="unauthorized-artifact",
                    authorization_scope=AUTHORIZED_SCOPE,
                )
            )


def test_all_operations_fail_closed_for_wrong_scope() -> None:
    adapter = DefensiveRepairAdapter()
    for operation in DefensiveRepairOperation:
        with pytest.raises(PermissionError, match="authorization scope"):
            adapter.invoke(
                DefensiveRepairRequest(
                    operation,
                    fixture_id=FIXTURE_ID,
                    authorization_scope="arbitrary-repository",
                )
            )


def test_capability_metadata_denies_authority_expansion() -> None:
    candidate = DefensiveRepairAdapter().capability_candidate()
    assert candidate.metadata == {
        "fixture_id": FIXTURE_ID,
        "authorization_scope": AUTHORIZED_SCOPE,
        "arbitrary_source_input": False,
        "network_targeting": False,
        "shell_authority": False,
    }


def test_adapter_evidence_hash_is_deterministic() -> None:
    adapter = DefensiveRepairAdapter()
    request = DefensiveRepairRequest(DefensiveRepairOperation.VERIFY)
    first = adapter.invoke(request)
    second = adapter.invoke(request)
    assert first == second
    assert first.evidence_sha256 == second.evidence_sha256
