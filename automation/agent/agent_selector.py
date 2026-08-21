"""Agent selector for Automation OS.

Selects verified candidate agents based on task requirements,
capability score, availability, and verification state.
"""

from dataclasses import dataclass


@dataclass
class AgentCandidate:
    agent_id: str
    capability_score: float
    verified: bool
    available: bool


def select_agent(candidates: list[AgentCandidate]):
    eligible = [c for c in candidates if c.verified and c.available]
    if not eligible:
        return None
    return max(eligible, key=lambda c: c.capability_score)


if __name__ == "__main__":
    print("Agent selector initialized")
