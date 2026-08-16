from __future__ import annotations

import pytest

from centinal26.evolution import DEFAULT_PROTECTED_PREFIXES, GoalSpec


@pytest.mark.parametrize(
    "path",
    [
        "src/centinal26/control_plane.py",
        "src/centinal26/provider_bridge.py",
    ],
)
def test_control_plane_kernels_are_protected_from_controlled_evolution(path: str) -> None:
    assert path in DEFAULT_PROTECTED_PREFIXES
    goal = GoalSpec.from_dict(
        {
            "schema": "centinal26-goal-v1",
            "goal_id": "protection-check",
            "objective": "Verify control-plane protection",
            "include_paths": ["src/centinal26"],
            "goal_tests": ["tests/test_control_plane_protection.py"],
            "allowed_change_prefixes": ["src/centinal26"],
        }
    )
    permitted, reason = goal.permits_changed_path(path)
    assert not permitted
    assert reason == f"protected:{path}"
