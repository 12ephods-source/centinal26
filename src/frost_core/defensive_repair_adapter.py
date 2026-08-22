from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from .capability_factory import CapabilityCandidate
from .defensive_repair_benchmark import (
    FIXTURE_ID,
    VULNERABLE_SOURCE,
    candidate_repair,
    independently_verify,
    reproduce,
)

AUTHORIZED_SCOPE = "repository-owned-fixture"


class DefensiveRepairOperation(StrEnum):
    AUDIT = "software.audit"
    REPRODUCE = "software.reproduce"
    REPAIR = "software.repair"
    VERIFY = "software.verify"


@dataclass(frozen=True)
class DefensiveRepairRequest:
    operation: DefensiveRepairOperation
    fixture_id: str = FIXTURE_ID
    authorization_scope: str = AUTHORIZED_SCOPE


@dataclass(frozen=True)
class DefensiveRepairResult:
    operation: str
    fixture_id: str
    status: str
    evidence: dict[str, object]

    @property
    def evidence_sha256(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


class DefensiveRepairAdapter:
    """Bounded adapter for the repository-owned known-ground-truth fixture only."""

    capability_id = "centinal26.defensive-repair.fixture-v1"

    def capability_candidate(self) -> CapabilityCandidate:
        return CapabilityCandidate(
            capability_id=self.capability_id,
            operation="software.audit|software.reproduce|software.repair|software.verify",
            source_identity=hashlib.sha256(VULNERABLE_SOURCE.encode("utf-8")).hexdigest(),
            adapter_identity="defensive-repair-adapter-v1",
            risk_class="bounded_local_fixture",
            provider_id="centinal26.local",
            schema_identity="defensive-repair-request-v1",
            metadata={
                "fixture_id": FIXTURE_ID,
                "authorization_scope": AUTHORIZED_SCOPE,
                "arbitrary_source_input": False,
                "network_targeting": False,
                "shell_authority": False,
            },
        )

    def invoke(self, request: DefensiveRepairRequest) -> DefensiveRepairResult:
        self._authorize(request)

        if request.operation == DefensiveRepairOperation.AUDIT:
            observation = reproduce(VULNERABLE_SOURCE)
            return DefensiveRepairResult(
                operation=request.operation.value,
                fixture_id=FIXTURE_ID,
                status="CANDIDATE" if observation["reproduced"] else "NO_FINDING",
                evidence={"reproducer": observation},
            )

        if request.operation == DefensiveRepairOperation.REPRODUCE:
            observation = reproduce(VULNERABLE_SOURCE)
            return DefensiveRepairResult(
                operation=request.operation.value,
                fixture_id=FIXTURE_ID,
                status="REPRODUCED" if observation["reproduced"] else "NOT_REPRODUCED",
                evidence={"reproducer": observation},
            )

        repair = candidate_repair(VULNERABLE_SOURCE)
        if request.operation == DefensiveRepairOperation.REPAIR:
            return DefensiveRepairResult(
                operation=request.operation.value,
                fixture_id=FIXTURE_ID,
                status="CANDIDATE_REPAIR",
                evidence={
                    "source_sha256": hashlib.sha256(
                        VULNERABLE_SOURCE.encode("utf-8")
                    ).hexdigest(),
                    "repair_sha256": hashlib.sha256(
                        repair["source"].encode("utf-8")
                    ).hexdigest(),
                    "patch_sha256": hashlib.sha256(
                        repair["patch"].encode("utf-8")
                    ).hexdigest(),
                },
            )

        if request.operation == DefensiveRepairOperation.VERIFY:
            verification = independently_verify(
                VULNERABLE_SOURCE, repair["source"], repair["patch"]
            )
            return DefensiveRepairResult(
                operation=request.operation.value,
                fixture_id=FIXTURE_ID,
                status=verification.status,
                evidence=json.loads(verification.evidence_json),
            )

        raise ValueError(f"unsupported operation: {request.operation}")

    @staticmethod
    def _authorize(request: DefensiveRepairRequest) -> None:
        if request.fixture_id != FIXTURE_ID:
            raise PermissionError("only the pinned repository-owned fixture is authorized")
        if request.authorization_scope != AUTHORIZED_SCOPE:
            raise PermissionError("authorization scope does not permit this operation")
