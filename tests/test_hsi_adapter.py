from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from centinal26.hsi_adapter import (
    HSIProtocolError,
    normalize_hsi_request,
    request_sha256,
    to_frost_call_envelope,
)

SHA = "a" * 64


def request(operation: str = "hsi.identify", parameters: dict | None = None) -> dict:
    if parameters is None:
        parameters = {"spec_ref": "cas:sha256:example", "spec_sha256": SHA}
    return {
        "protocol_version": "hsi/1.0",
        "request_id": "hsi-1",
        "operation": operation,
        "parameters": parameters,
        "caller": {"type": "test", "id": "tester"},
        "provenance": {"suite": "test_hsi_adapter"},
    }


def test_identify_maps_to_typed_frost_call_capability() -> None:
    normalized = normalize_hsi_request(request())
    envelope = to_frost_call_envelope(normalized)
    assert envelope["operation"] == "intent.submit"
    assert envelope["parameters"]["capability"] == "hsi.identify"
    assert envelope["parameters"]["payload"]["spec_sha256"] == SHA
    assert envelope["parameters"]["constraints"]["no_arbitrary_shell"] is True


def test_run_is_bounded_and_deterministic() -> None:
    raw = request(
        "hsi.run",
        {
            "spec_ref": "cas:sha256:example",
            "spec_sha256": SHA,
            "backend": "branch2-v1.5",
            "runs": 12,
            "seed": 7,
            "objective": "nevsi",
        },
    )
    left = normalize_hsi_request(raw)
    right = normalize_hsi_request(json.loads(json.dumps(raw)))
    assert left == right
    assert request_sha256(left) == request_sha256(right)
    assert left.parameters["runs"] == 12


def test_arbitrary_execution_fields_are_rejected() -> None:
    raw = request("hsi.run", {"spec_ref": "x", "spec_sha256": SHA, "command": "rm -rf /"})
    with pytest.raises(HSIProtocolError, match="prohibited execution fields"):
        normalize_hsi_request(raw)


@pytest.mark.parametrize("operation", ["shell.exec", "device.reboot", "hsi.delete"])
def test_unsupported_operations_fail_closed(operation: str) -> None:
    with pytest.raises(HSIProtocolError, match="unsupported HSI operation"):
        normalize_hsi_request(request(operation))


def test_invalid_hash_fails_closed() -> None:
    with pytest.raises(HSIProtocolError, match="SHA-256"):
        normalize_hsi_request(request(parameters={"spec_ref": "x", "spec_sha256": "bad"}))


def test_runs_are_bounded() -> None:
    with pytest.raises(HSIProtocolError, match="runs"):
        normalize_hsi_request(
            request("hsi.run", {"spec_ref": "x", "spec_sha256": SHA, "runs": 1_000_001})
        )


def test_verify_accepts_only_typed_artifact_reference() -> None:
    r = normalize_hsi_request(
        request(
            "hsi.verify",
            {
                "artifact_ref": "cas:sha256:evidence",
                "artifact_sha256": SHA,
                "verification_type": "evidence_chain",
            },
        )
    )
    assert r.parameters["verification_type"] == "evidence_chain"
