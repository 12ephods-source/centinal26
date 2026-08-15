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


def test_every_new_result_is_independently_verified_before_publication() -> None:
    text = workflow_text()
    assert "runtime/verifications" in text
    assert "callable-worker-v1.0.0/verifier.js" in text
    assert 'verifier.js "$req" "$out" "$verification"' in text
    assert "git add runtime/results runtime/verifications" in text


def test_existing_unverified_results_are_verified_without_reexecution() -> None:
    text = workflow_text()
    assert 'if [[ -e "$out" ]]; then' in text
    assert 'if [[ ! -e "$verification" ]]; then' in text
    assert "verified=$((verified + 1))" in text


def test_result_publication_has_bounded_reconciliation_retry() -> None:
    text = workflow_text()
    assert "for attempt in 1 2 3; do" in text
    assert "git fetch origin callable-runtime" in text
    assert "git rebase origin/callable-runtime" in text
    assert "git push origin HEAD:callable-runtime" in text
    assert "result reconciliation failed after 3 attempts" in text


def test_idle_runs_do_not_publish_fake_results() -> None:
    text = workflow_text()
    assert "steps.worker.outputs.processed != '0' || steps.worker.outputs.verified != '0'" in text
    assert "processed=$processed" in text
    assert "verified=$verified" in text
    assert "pending_before=$pending_before" in text
