import subprocess

SCRIPT = "tools/dedupe-organizer/device_zero_precondition.sh"
PIN = "18941855035ec0bc463a40283e4893a724a7dae2"
RUNTIME_SHA = "ac8560aa3cb077ca100f204604f2f98ea10bb03c9b7dc6b17c6c10e07d41404f"


def _script_text() -> str:
    with open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


def test_device_zero_precondition_bash_syntax() -> None:
    subprocess.run(["bash", "-n", SCRIPT], check=True)


def test_device_zero_precondition_pins_exact_release() -> None:
    text = _script_text()
    assert PIN in text
    assert RUNTIME_SHA in text
    assert "git -C \"$TMP/repo\" checkout --quiet --detach \"$PIN\"" in text
    assert "source pin mismatch" in text
    assert "runtime SHA-256 mismatch" in text


def test_device_zero_precondition_requires_real_termux() -> None:
    text = _script_text()
    assert "Android environment not detected" in text
    assert "Termux environment not detected" in text
    assert "shared storage permission not yet granted" in text


def test_device_zero_precondition_installs_submission_dependency() -> None:
    text = _script_text()
    assert "pkg install -y git python coreutils gh" in text


def test_device_zero_precondition_preserves_bounded_execution() -> None:
    text = _script_text()
    assert "eval " not in text
    assert "bash -c" not in text
    assert "curl |" not in text
    assert 'exec "$AUTOPILOT"' in text
