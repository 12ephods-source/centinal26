from __future__ import annotations

from centinal26.evolution import DEFAULT_PROTECTED_PREFIXES, GoalSpec


def test_control_plane_kernel_is_protected_from_controlled_evolution() -> None:
    assert "src/centinal26/control_plane.py" in DEFAULT_PROTECTED_PREFIXES
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
    permitted, reason = goal.permits_changed_path("src/centinal26/control_plane.py")
    assert not permitted
    assert reason == "protected:src/centinal26/control_plane.py"
