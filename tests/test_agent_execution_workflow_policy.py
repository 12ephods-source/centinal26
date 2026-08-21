WORKFLOW = ".github/workflows/agent-execution.yml"


def workflow_text() -> str:
    with open(WORKFLOW, encoding="utf-8") as handle:
        return handle.read()


def test_reusable_agent_workflow_uses_named_profiles_not_arbitrary_command_input() -> None:
    text = workflow_text()
    assert "      command:\n" not in text
    assert "      profile:\n" in text
    for profile in ("agent-tests", "full-tests", "lint", "fleet-qualify"):
        assert profile in text


def test_agent_workflow_persists_machine_and_human_status_evidence() -> None:
    text = workflow_text()
    assert "issues: write" in text
    assert "agent_status.json" in text
    assert "agent_evidence.json" in text
    assert "frost-agent-execution-ledger-v1" in text
    assert "Update durable status ledger" in text
    assert "Enforce execution result" in text
