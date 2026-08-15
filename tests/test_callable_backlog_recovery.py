from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "callable-fabric-worker.yml"
QUEUE_PLAN = (
    Path(__file__).parents[1]
    / "deploy"
    / "github"
    / "callable-worker-v1.0.0"
    / "queue-plan.js"
)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def queue_plan_text() -> str:
    return QUEUE_PLAN.read_text(encoding="utf-8")


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
    assert 'FROST_CALLABLE_MAX_BATCH: "128"' in text
    assert '--max-batch "$FROST_CALLABLE_MAX_BATCH"' in text


def test_every_new_result_is_independently_verified_before_publication() -> None:
    text = workflow_text()
    assert "runtime/verifications" in text
    assert "callable-worker-v1.0.0/verifier.js" in text
    assert 'verifier.js "$req" "$out" "$verification"' in text
    assert "git add runtime/results runtime/verifications" in text


def test_existing_unverified_results_are_verified_without_reexecution() -> None:
    text = workflow_text()
    plan = queue_plan_text()
    assert "verify_missing" in plan
    assert "if (!hasVerification)" in plan
    assert "done < <(plan_items verify_missing)" in text
    assert '"$req" "runtime/results/$base" "runtime/verifications/$base"' in text


def test_changed_completed_request_is_reverified_without_reexecution() -> None:
    text = workflow_text()
    plan = queue_plan_text()
    assert "reverify_existing" in plan
    assert "eventName === 'push'" in plan
    assert "done < <(plan_items reverify_existing)" in text
    assert 'tmp_verification="$(mktemp)"' in text


def test_push_uses_incremental_commit_range_with_full_scan_fallback() -> None:
    text = workflow_text()
    plan = queue_plan_text()
    assert '--before "${{ github.event.before }}"' in text
    assert '--head "${{ github.sha }}"' in text
    assert "git-diff-failed" in plan
    assert "commit-range-unavailable" in plan
    assert "listAllRequests(root)" in plan


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
    assert "reverified=$reverified" in text
    assert "cat \"${{ steps.plan.outputs.plan_file }}\"" in text


def test_provider_attestation_uses_checked_out_runtime_identity() -> None:
    text = workflow_text()
    assert 'checked_out_sha="$(git rev-parse HEAD)"' in text
    assert 'checked_out_ref="refs/heads/callable-runtime"' in text
    assert 'GITHUB_SHA="$checked_out_sha" GITHUB_REF="$checked_out_ref"' in text
    assert 'node deploy/github/callable-worker-v1.0.0/worker.js "$req" "$out"' in text
