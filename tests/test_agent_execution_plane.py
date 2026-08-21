from tools.agent_execution_plane import authorize, select_role


def test_builder_gets_bounded_repository_authority() -> None:
    result = authorize("builder", "write:repository_file", consequential=True)
    assert result.status == "AUTHORIZED_BOUNDED"
    assert result.requires_judge is True


def test_recovery_root_is_denied_to_every_agent() -> None:
    for role in ("planner", "builder", "judge", "sre", "sentinel", "release"):
        result = authorize(role, "authentication_or_recovery_factor_change")
        assert result.status == "ROOT_DENY"


def test_judge_is_non_mutating_by_default() -> None:
    result = authorize("judge", "write:repository_file")
    assert result.status == "DENY_ROLE_MODE"


def test_role_selection() -> None:
    assert select_role("build") == "builder"
    assert select_role("verify") == "judge"
    assert select_role("repair") == "sre"
    assert select_role("audit") == "sentinel"
