from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "automation" / "device" / "clipboard_autorun.py"
INSTALLER = (
    ROOT / "deploy" / "termux" / "FROST_CLIPBOARD_AUTORUN_ONE_PASTE_v1.0.sh"
)


def load_module():
    spec = importlib.util.spec_from_file_location("clipboard_autorun", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_marker_is_required_and_exact() -> None:
    module = load_module()
    try:
        module.canonical_input("echo nope\n")
    except ValueError as exc:
        assert "not marked" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unmarked clipboard unexpectedly accepted")

    try:
        module.canonical_input("# FROST-AUTORUN:1evil\necho nope\n")
    except ValueError as exc:
        assert "not marked" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("marker prefix unexpectedly accepted")


def test_bash_and_python_markers_are_parsed() -> None:
    module = load_module()
    shell, body = module.canonical_input(
        "# FROST-AUTORUN:1\nprintf 'ok\\n'\n"
    )
    assert shell == "bash"
    assert body == "printf 'ok\\n'\n"

    shell, body = module.canonical_input(
        "# FROST-AUTORUN:1 shell=python\nprint('ok')\n"
    )
    assert shell == "python"
    assert body == "print('ok')\n"


def test_chatgpt_code_fence_is_removed() -> None:
    module = load_module()
    shell, body = module.canonical_input(
        "```bash\n# FROST-AUTORUN:1\nprintf 'fenced\\n'\n```"
    )
    assert shell == "bash"
    assert body == "printf 'fenced\\n'\n"


def test_receiver_stages_then_executes_marked_bash(tmp_path: Path) -> None:
    env = dict(os.environ)
    state = tmp_path / "state"
    env["FROST_CLIPBOARD_STATE_ROOT"] = str(state)
    script = "# FROST-AUTORUN:1\nprintf 'AUTORUN_PASS\\n'\n"

    staged = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--stage"],
        input=script,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert staged.returncode == 0
    assert "FROST_AUTORUN_STAGED" in staged.stdout
    assert (state / "pending.json").is_file()
    assert list((state / "inbox").glob("*.clipboard.txt"))
    assert list((state / "inbox").glob("*.sh"))

    executed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--run-pending"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert executed.returncode == 0
    assert "AUTORUN_PASS" in executed.stdout
    assert "--- script ---" in executed.stdout
    assert not (state / "pending.json").exists()
    assert list((state / "runs").glob("*.json"))
    assert list((state / "runs").glob("*.log"))


def test_unmarked_clipboard_is_ignored_without_staging(tmp_path: Path) -> None:
    env = dict(os.environ)
    state = tmp_path / "state"
    env["FROST_CLIPBOARD_STATE_ROOT"] = str(state)
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--stage"],
        input="printf 'MUST_NOT_RUN\\n'\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0
    assert "FROST_AUTORUN_IGNORED" in completed.stdout
    assert "MUST_NOT_RUN" not in completed.stdout
    assert not (state / "pending.json").exists()
    assert not list((state / "inbox").glob("*"))


def test_pending_script_hash_is_reverified_before_execution(tmp_path: Path) -> None:
    env = dict(os.environ)
    state = tmp_path / "state"
    env["FROST_CLIPBOARD_STATE_ROOT"] = str(state)
    staged = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--stage"],
        input="# FROST-AUTORUN:1\nprintf 'safe\\n'\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert staged.returncode == 0
    script_path = next((state / "inbox").glob("*.sh"))
    script_path.write_text("printf 'tampered\\n'\n", encoding="utf-8")
    executed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--run-pending"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert executed.returncode == 2
    assert "SHA-256 mismatch" in executed.stdout
    assert "tampered" not in executed.stdout


def test_installer_uses_two_phase_tasker_bridge_without_global_external_apps() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "frost_clipboard_stage" in text
    assert "frost_clipboard_run" in text
    assert "Stdin: %cl_text" in text
    assert "Execute in a terminal session: OFF" in text
    assert "Execute in a terminal session: ON" in text
    assert "FROST_AUTORUN_STAGED" in text
    assert "Event -> Clipboard Changed" in text
    assert "# FROST-AUTORUN:1" in text
    assert "allow-external-apps=true" not in text
    assert "TASKER_DIR" in text
