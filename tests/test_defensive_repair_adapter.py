import pytest

from frost_core.defensive_repair_adapter import (
    AUTHORIZED_SCOPE,
    DefensiveRepairAdapter,
    DefensiveRepairOperation,
    DefensiveRepairRequest,
)
from frost_core.defensive_repair_benchmark import FIXTURE_ID


def test_adapter_exposes_only_bounded_local_fixture_capability() -> None:
    candidate = DefensiveRepairAdapter().capability_candidate()
    assert candidate.risk_class == "bounded_local_fixture"
    assert candidate.metadata["arbitrary_source_input"] is False
    assert candidate.metadata["network_targeting"] is False
    assert candidate.metadata["shell_authority"] is False


def test_adapter_runs_candidate_reproduce_repair_verify_lifecycle() -> None:
    adapter = DefensiveRepairAdapter()

    audit = adapter.invoke(DefensiveRepairRequest(DefensiveRepairOperation.AUDIT))
    reproduced = adapter.invoke(DefensiveRepairRequest(DefensiveRepairOperation.REPRODUCE))
    repair = adapter.invoke(DefensiveRepairRequest(DefensiveRepairOperation.REPAIR))
    verified = adapter.invoke(DefensiveRepairRequest(DefensiveRepairOperation.VERIFY))

    assert audit.status == "CANDIDATE"
    assert reproduced.status == "REPRODUCED"
    assert repair.status == "CANDIDATE_REPAIR"
    assert verified.status == "INDEPENDENTLY_VERIFIED"
    assert len(repair.evidence_sha256) == 64


def test_adapter_rejects_unpinned_fixture() -> None:
    adapter = DefensiveRepairAdapter()
    with pytest.raises(PermissionError, match="pinned repository-owned fixture"):
        adapter.invoke(
            DefensiveRepairRequest(
                DefensiveRepairOperation.AUDIT,
                fixture_id="arbitrary-target",
            )
        )


def test_adapter_rejects_wrong_authorization_scope() -> None:
    adapter = DefensiveRepairAdapter()
    with pytest.raises(PermissionError, match="authorization scope"):
        adapter.invoke(
            DefensiveRepairRequest(
                DefensiveRepairOperation.VERIFY,
                fixture_id=FIXTURE_ID,
                authorization_scope=AUTHORIZED_SCOPE + "-expanded",
            )
        )
