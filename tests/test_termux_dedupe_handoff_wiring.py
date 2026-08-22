import subprocess

INSTALLER = "deploy/termux/library_cleaner/install_autopilot.sh"


def _text() -> str:
    with open(INSTALLER, encoding="utf-8") as handle:
        return handle.read()


def test_installer_bash_syntax() -> None:
    subprocess.run(["bash", "-n", INSTALLER], check=True)


def test_installer_wires_exact_dedupe_handoff() -> None:
    text = _text()
    assert "tools/dedupe-organizer/device_zero_precondition.sh" in text
    assert 'install -m 0700 "$DEDUPE_HANDOFF_SOURCE" "$DEDUPE_HANDOFF"' in text
    assert 'nohup "$DEDUPE_HANDOFF"' in text
    assert "Dedupe device acceptance handoff started." in text


def test_installer_keeps_termux_gate_and_bounded_execution() -> None:
    text = _text()
    assert '"${PREFIX:-}" == *com.termux*' in text
    assert "eval " not in text
    assert "curl |" not in text
