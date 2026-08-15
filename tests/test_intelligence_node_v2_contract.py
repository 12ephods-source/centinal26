from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_node_v2_has_watchdog_heartbeat_retry_and_doctor():
    node = text("termux/intelligence_node.sh")
    assert 'NODE_VERSION="2.0.0"' in node
    assert "HEARTBEAT_INTERVAL" in node
    assert "WORKER_INTERVAL" in node
    assert "MAX_BACKOFF" in node
    assert "ensure_controller" in node
    assert "heartbeat_once" in node
    assert "doctor()" in node
    assert "safe_upgrade()" in node
    assert "merge --ff-only origin/main" in node


def test_node_process_identity_is_not_pidfile_only():
    node = text("termux/intelligence_node.sh")
    supervisor = text("termux/intelligence_controller_supervisor.sh")
    assert "/proc/$pid/stat" in node
    assert "intelligence_node.sh*run" in node
    assert "/proc/$pid/stat" in supervisor
    assert "centinal26-intelligence*daemon" in supervisor


def test_worker_remains_allowlisted_and_checks_minimum_commit():
    worker = text("termux/intelligence_controller_github_worker_once.sh")
    assert 'ALLOWED_COMMAND="automation_project_finalize_v1"' in worker
    assert "DENIED_UNSUPPORTED_COMMAND" in worker
    assert "minimum_merge_commit" in worker
    assert "merge-base --is-ancestor" in worker
    assert "--connect-timeout 10" in worker
    assert "--max-time 30" in worker


def test_node_does_not_add_arbitrary_shell_or_remote_reboot():
    combined = "\n".join(
        text(path)
        for path in (
            "termux/intelligence_node.sh",
            "termux/intelligence_controller_supervisor.sh",
            "termux/intelligence_controller_github_worker_once.sh",
            "termux/intelligence_controller_report_after_reboot.sh",
        )
    )
    for token in ("sudo reboot", "termux-reboot", 'eval "$', 'bash -c "$command', "sh -c \"$command"):
        assert token not in combined


def test_installer_boot_hooks_route_through_node_v2():
    installer = text("termux/install_intelligence_github_control.sh")
    assert 'NODE="$ROOT/termux/intelligence_node.sh"' in installer
    assert '"$NODE" boot' in installer
    assert '"$NODE" kick' in installer
    assert '"$NODE" doctor' in installer
    assert "BLOCKED_LOCAL_CHANGES" in installer
