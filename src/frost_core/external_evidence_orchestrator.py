from __future__ import annotations

from dataclasses import dataclass

from frost_core.compute_router import ComputeProvider, RoutingDecision, Workload, route_workload
from frost_core.external_evidence_gates import EvidenceCandidate, GateStatus, GateType, evaluate_gate


@dataclass(frozen=True)
class OrchestratedWork:
    workload: Workload
    routing: RoutingDecision


@dataclass(frozen=True)
class OrchestrationState:
    gates: dict[GateType, GateStatus]
    work: tuple[OrchestratedWork, ...]


def orchestrate(
    gate_candidates: dict[GateType, tuple[EvidenceCandidate, ...]],
    workloads: tuple[Workload, ...],
    providers: tuple[ComputeProvider, ...],
) -> OrchestrationState:
    gates = {
        gate_type: evaluate_gate(gate_type, gate_candidates.get(gate_type, ())).status
        for gate_type in GateType
    }
    satisfied = frozenset(
        gate_type.value
        for gate_type, status in gates.items()
        if status is GateStatus.SATISFIED
    )
    work = tuple(
        OrchestratedWork(
            workload=workload,
            routing=route_workload(
                workload,
                providers,
                satisfied_external_gates=satisfied,
            ),
        )
        for workload in workloads
    )
    return OrchestrationState(gates=gates, work=work)
