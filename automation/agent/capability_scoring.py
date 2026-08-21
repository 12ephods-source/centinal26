"""Capability scoring scaffold.

Converts discovered application capability candidates into ranked records.
This does not activate agents or grant permissions.
"""

from dataclasses import asdict, dataclass


@dataclass
class CapabilityScore:
    capability: str
    evidence: float
    relevance: float
    readiness: float
    score: float
    status: str = "PENDING_VERIFICATION"


def score_capability(evidence: float, relevance: float, readiness: float) -> float:
    return (evidence * 0.4) + (relevance * 0.4) + (readiness * 0.2)


def rank_capabilities(items: list[CapabilityScore]):
    return sorted(items, key=lambda x: x.score, reverse=True)


if __name__ == "__main__":
    example = CapabilityScore(
        capability="automation",
        evidence=0.5,
        relevance=0.8,
        readiness=0.4,
        score=score_capability(0.5, 0.8, 0.4),
    )
    print(asdict(example))
