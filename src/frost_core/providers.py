from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ProviderMaturity(IntEnum):
    DISCOVERED = 0
    HOST_VALIDATED = 1
    CONNECTED_VALIDATED = 2
    DEVICE_VALIDATED = 3
    ENDURANCE_VALIDATED = 4
    PROMOTED = 5
    DEFAULT_ELIGIBLE = 6


class ProviderAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProviderRecord:
    provider_id: str
    provider_type: str
    capabilities: tuple[str, ...]
    maturity: ProviderMaturity
    availability: ProviderAvailability = ProviderAvailability.UNKNOWN
    deployment_identity: str | None = None
    source_identity: str | None = None
    health: float = 0.0
    latency_ms: float | None = None
    cost_rank: int = 100
    limitations: tuple[str, ...] = ()
    metadata: Json = field(default_factory=dict)
    updated_at: str = field(default_factory=_now)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities or "*" in self.capabilities


@dataclass(frozen=True)
class RoutingPolicy:
    minimum_maturity: ProviderMaturity = ProviderMaturity.HOST_VALIDATED
    preferred_provider_ids: tuple[str, ...] = ()
    allowed_provider_types: tuple[str, ...] = ()
    allow_degraded: bool = False
    max_latency_ms: float | None = None
    max_cost_rank: int | None = None
    require_source_identity: bool = True


@dataclass(frozen=True)
class RouteDecision:
    capability: str
    provider: ProviderRecord
    candidates_considered: tuple[str, ...]
    rationale: tuple[str, ...]


class ProviderRegistry:
    """Durable provider inventory with explicit, policy-bound routing.

    There is deliberately no implicit global default. A caller must provide a routing
    policy for every selection so the presence of a provider cannot silently make it
    authoritative for all capabilities.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                provider_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    def upsert(self, record: ProviderRecord) -> None:
        if not record.provider_id.strip() or not record.provider_type.strip():
            raise ValueError("provider_id and provider_type are required")
        if not record.capabilities:
            raise ValueError("provider must declare at least one capability")
        if not 0.0 <= record.health <= 1.0:
            raise ValueError("health must be between 0 and 1")
        body = asdict(record)
        body["maturity"] = record.maturity.name
        body["availability"] = record.availability.value
        self.db.execute(
            """
            INSERT INTO providers(provider_id,record_json,updated_at) VALUES(?,?,?)
            ON CONFLICT(provider_id) DO UPDATE SET
              record_json=excluded.record_json,
              updated_at=excluded.updated_at
            """,
            (record.provider_id, json.dumps(body, sort_keys=True), _now()),
        )
        self.db.commit()

    def get(self, provider_id: str) -> ProviderRecord:
        row = self.db.execute(
            "SELECT record_json FROM providers WHERE provider_id=?", (provider_id,)
        ).fetchone()
        if row is None:
            raise KeyError(provider_id)
        return self._decode(row["record_json"])

    def list(self) -> list[ProviderRecord]:
        rows = self.db.execute("SELECT record_json FROM providers ORDER BY provider_id").fetchall()
        return [self._decode(row["record_json"]) for row in rows]

    def select(self, capability: str, policy: RoutingPolicy) -> RouteDecision:
        if not capability.strip():
            raise ValueError("capability must not be empty")
        candidates: list[ProviderRecord] = []
        rejected: list[str] = []
        for record in self.list():
            reason = self._reject_reason(record, capability, policy)
            if reason is None:
                candidates.append(record)
            else:
                rejected.append(f"{record.provider_id}:{reason}")
        if not candidates:
            detail = ", ".join(rejected) if rejected else "registry empty"
            raise LookupError(f"no provider satisfies routing policy ({detail})")

        preference = {
            provider_id: index
            for index, provider_id in enumerate(policy.preferred_provider_ids)
        }

        def key(record: ProviderRecord) -> tuple[Any, ...]:
            preferred_rank = preference.get(record.provider_id, len(preference) + 1)
            availability_rank = {
                ProviderAvailability.AVAILABLE: 0,
                ProviderAvailability.DEGRADED: 1,
                ProviderAvailability.UNKNOWN: 2,
                ProviderAvailability.UNAVAILABLE: 3,
            }[record.availability]
            latency = float("inf") if record.latency_ms is None else record.latency_ms
            return (
                preferred_rank,
                availability_rank,
                -int(record.maturity),
                -record.health,
                record.cost_rank,
                latency,
                record.provider_id,
            )

        chosen = min(candidates, key=key)
        rationale = [
            f"maturity>={policy.minimum_maturity.name}",
            f"availability={chosen.availability.value}",
            f"health={chosen.health:.3f}",
            f"cost_rank={chosen.cost_rank}",
        ]
        if chosen.provider_id in preference:
            rationale.append(f"preferred_rank={preference[chosen.provider_id]}")
        return RouteDecision(
            capability=capability,
            provider=chosen,
            candidates_considered=tuple(record.provider_id for record in candidates),
            rationale=tuple(rationale),
        )

    @staticmethod
    def _reject_reason(
        record: ProviderRecord,
        capability: str,
        policy: RoutingPolicy,
    ) -> str | None:
        if not record.supports(capability):
            return "unsupported_capability"
        if record.maturity < policy.minimum_maturity:
            return "insufficient_maturity"
        if record.availability == ProviderAvailability.UNAVAILABLE:
            return "unavailable"
        if record.availability == ProviderAvailability.DEGRADED and not policy.allow_degraded:
            return "degraded_disallowed"
        if (
            policy.allowed_provider_types
            and record.provider_type not in policy.allowed_provider_types
        ):
            return "provider_type_disallowed"
        if policy.max_latency_ms is not None:
            if record.latency_ms is None or record.latency_ms > policy.max_latency_ms:
                return "latency_bound"
        if policy.max_cost_rank is not None and record.cost_rank > policy.max_cost_rank:
            return "cost_bound"
        if policy.require_source_identity and not record.source_identity:
            return "missing_source_identity"
        return None

    @staticmethod
    def _decode(body: str) -> ProviderRecord:
        data = json.loads(body)
        data["maturity"] = ProviderMaturity[data["maturity"]]
        data["availability"] = ProviderAvailability(data["availability"])
        data["capabilities"] = tuple(data["capabilities"])
        data["limitations"] = tuple(data["limitations"])
        return ProviderRecord(**data)
