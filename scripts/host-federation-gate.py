#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from frost_core.capability_factory import (
    CapabilityCandidate,
    CapabilityFactoryLedger,
    CapabilityStage,
    GateEvidence,
    REQUIRED_PROMOTION_GATES,
)
from frost_core.effects import EffectAuthorization, EffectProtocolLedger, EffectRequest, EffectState
from frost_core.providers import (
    ProviderAvailability,
    ProviderMaturity,
    ProviderRecord,
    ProviderRegistry,
    RoutingPolicy,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded Frost CORE host federation gates")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def run(iterations: int) -> dict[str, object]:
    if iterations < 1 or iterations > 100_000:
        raise ValueError("iterations must be between 1 and 100000")
    with tempfile.TemporaryDirectory(prefix="frost-federation-gate-") as temp:
        root = Path(temp)
        effects = EffectProtocolLedger(root / "effects.sqlite")
        providers = ProviderRegistry(root / "providers.sqlite")
        factory = CapabilityFactoryLedger(root / "factory.sqlite")

        providers.upsert(
            ProviderRecord(
                "host-test",
                "local",
                ("diagnostics.effect",),
                ProviderMaturity.HOST_VALIDATED,
                ProviderAvailability.AVAILABLE,
                source_identity="sha256:host-test",
                health=1.0,
                latency_ms=1.0,
                cost_rank=0,
            )
        )
        route = providers.select("diagnostics.effect", RoutingPolicy())

        for index in range(iterations):
            request = EffectRequest(
                "diagnostics.effect",
                {"index": index},
                f"host-gate:{index}",
                request_id=f"host-gate-request:{index}",
            )
            effect_id, created = effects.submit(request, max_attempts=2)
            if not created:
                raise RuntimeError("fresh host-gate request unexpectedly deduplicated")
            authorization = EffectAuthorization(
                authorization_id=f"auth:{index}",
                request_sha256=request.sha256,
                capability=request.capability,
                actor="host-federation-gate",
                approved=True,
                expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            )
            if effects.authorize(effect_id, authorization) != EffectState.AUTHORIZED:
                raise RuntimeError("authorization gate failed")
            claim = effects.claim("host-worker", lease_seconds=30)
            if claim is None or claim.effect_id != effect_id:
                raise RuntimeError("claim gate failed")
            token = effects.begin_execution(
                claim,
                provider_id=route.provider.provider_id,
                provider_idempotency_key=f"provider:{index}",
                operation="diagnostics.effect",
            )
            effects.record_execution(
                effect_id,
                token,
                {"index": index, "ok": True},
                {"provider": "host-test", "id": f"receipt:{index}"},
            )
            effects.verify(
                effect_id,
                verifier_id="host-independent-verifier",
                passed=True,
                evidence={"index": index, "matches": True},
                independent=True,
            )
            effects.publish(effect_id, {"result_ref": f"host:{index}"})
            effects.acknowledge(effect_id, {"delivery_id": f"delivery:{index}"})

        candidate = CapabilityCandidate(
            capability_id="host-gate-capability",
            operation="diagnostics.effect",
            source_identity="sha256:host-source",
            adapter_identity="sha256:host-adapter",
            risk_class="read_only",
            provider_id="host-test",
            schema_identity="sha256:host-schema",
        )
        factory.discover(candidate)
        for stage in (
            CapabilityStage.WRAPPED,
            CapabilityStage.BUILDABLE,
            CapabilityStage.TESTED,
            CapabilityStage.DEPLOYED,
        ):
            factory.advance_structural(candidate.capability_id, stage)
        for gate in REQUIRED_PROMOTION_GATES:
            factory.record_gate(candidate.capability_id, GateEvidence(gate, True, {"host": True}))
        promotion = factory.evaluate(candidate.capability_id)

        counts = effects.counts()
        passed = (
            counts.get(EffectState.ACKNOWLEDGED.value) == iterations
            and effects.verify_audit_chain()
            and promotion.new_stage.value == "PROMOTED"
        )
        return {
            "schema": "frost-host-federation-gate/1.0",
            "passed": passed,
            "iterations": iterations,
            "effect_counts": counts,
            "effect_audit_chain": effects.verify_audit_chain(),
            "selected_provider": route.provider.provider_id,
            "capability_stage": promotion.new_stage.value,
            "external_side_effects_executed": False,
            "physical_android_validated": False,
        }


def main() -> int:
    args = parse_args()
    report = run(args.iterations)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if bool(report["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
