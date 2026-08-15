from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "callable-fabric-worker.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_backlog_recovery_has_push_manual_and_scheduled_wakeups() -> None:
    text = workflow_text()
    assert 'branches: ["callable-runtime"]' in text
    assert "workflow_dispatch:" in text
    assert 'cron: "17 * * * *"' in text


def test_every_trigger_checks_out_the_callable_runtime_branch() -> None:
    text = workflow_text()
    assert "ref: callable-runtime" in text
    assert "fetch-depth: 0" in text


def test_worker_is_serialized_and_bounded() -> None:
    text = workflow_text()
    assert "group: frost-callable-fabric-callable-runtime" in text
    assert "cancel-in-progress: false" in text
    assert "timeout-minutes: 20" in text


def test_result_publication_has_bounded_reconciliation_retry() -> None:
    text = workflow_text()
    assert "for attempt in 1 2 3; do" in text
    assert "git fetch origin callable-runtime" in text
    assert "git rebase origin/callable-runtime" in text
    assert "git push origin HEAD:callable-runtime" in text
    assert "result reconciliation failed after 3 attempts" in text


def test_idle_runs_do_not_publish_fake_results() -> None:
    text = workflow_text()
    assert "if: steps.worker.outputs.processed != '0'" in text
    assert "processed=$processed" in text
    assert "pending_before=$pending_before" in text
