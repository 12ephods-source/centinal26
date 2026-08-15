from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_physical_gate_requires_real_termux_and_reboot_change():
    gate = text("termux/intelligence_controller_physical_gate.sh")
    assert "com.termux" in gate
    assert 'post_boot" != "$pre_boot' in gate
    assert "Termux:Boot controller evidence missing" in gate
    assert "event_chain_valid" in gate
    assert "expired lease recovery" in gate


def test_gate_does_not_remote_reboot_or_enable_arbitrary_shell():
    combined = "\n".join(
        text(path)
        for path in (
            "termux/intelligence_controller_physical_gate.sh",
            "termux/intelligence_controller_supervisor.sh",
            "termux/intelligence_controller_github_worker_once.sh",
            "termux/intelligence_controller_report_after_reboot.sh",
        )
    )
    forbidden = ("sudo reboot", "termux-reboot", 'eval "$', 'bash -c "$command')
    for token in forbidden:
        assert token not in combined


def test_github_worker_is_command_allowlisted():
    worker = text("termux/intelligence_controller_github_worker_once.sh")
    assert "intelligence_controller_physical_gate_v1" in worker
    assert "automation.github_job/v2" in worker
    assert "issues?state=open" in worker


def test_installer_creates_separate_controller_worker_and_report_boot_hooks():
    installer = text("termux/install_intelligence_github_control.sh")
    assert "centinal26-intelligence-controller.sh" in installer
    assert "centinal26-intelligence-job.sh" in installer
    assert "centinal26-intelligence-report.sh" in installer
    assert "gh auth login" in installer
