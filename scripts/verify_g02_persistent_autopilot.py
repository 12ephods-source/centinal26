"""Independent black-box verifier for account goal G02.

The verifier does not import the persistent-autopilot implementation. It checks
public shell entry points, constructs its own isolated recovery fixture, observes
process/status behavior, and preserves physical Android validation as a separate
stronger gate.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "deploy" / "termux" / "FROST_ANDROID_WORKER_SELF_RECOVERY_v1.0.sh"
AUTOPILOT_INSTALLER = ROOT / "deploy" / "termux" / "library_cleaner" / "install_autopilot.sh"


class VerificationFailure(RuntimeError):
    """Raised when an independently observed G02 invariant fails."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _status(state: Path) -> dict[str, object]:
    path = state / "status.json"
    _assert(path.is_file(), f"missing status artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    _assert(isinstance(value, dict), "status artifact is not an object")
    return value


def _pid(root: Path) -> int:
    value = int((root / "state" / "fleet_worker.pid").read_text().strip())
    os.kill(value, 0)
    return value


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _static_contract() -> dict[str, str]:
    recovery = RECOVERY.read_text(encoding="utf-8")
    installer = AUTOPILOT_INSTALLER.read_text(encoding="utf-8")
    for path in (RECOVERY, AUTOPILOT_INSTALLER):
        check = _run(["bash", "-n", str(path)])
        _assert(check.returncode == 0, f"bash syntax failed for {path}: {check.stderr}")

    _assert(
        "repo_trusted" in recovery
        and 'git -C "$REPO" show "HEAD:$BOOTSTRAP_REL"' in recovery,
        "worker repair is not bound to tracked source identity",
    )
    _assert(
        'local_sha="$(sha256sum "$BOOTSTRAP"' in recovery,
        "worker repair lacks local source hashing",
    )
    _assert(
        "install_watchdog" in recovery and "pgrep -f" in recovery,
        "boot watchdog lacks duplicate-process guard",
    )
    _assert(
        "worker_running" in recovery and 'kill -0 "$pid"' in recovery,
        "worker health is not PID checked",
    )
    _assert(
        'case "${PREFIX:-}" in *com.termux*)' in recovery,
        "worker recovery lacks Termux gate",
    )

    _assert(
        "start_once()" in installer and 'kill -0 "$oldpid"' in installer,
        "autopilot controller start is not idempotent",
    )
    _assert(
        'start_once "$WATCH_PID"' in installer and 'start_once "$DASH_PID"' in installer,
        "persistent controllers bypass the idempotent start helper",
    )
    _assert(
        'install -m 0644 "$SOURCE_DIR/autopilot_cycle.py"' in installer,
        "installer does not refresh its bounded autopilot implementation",
    )
    _assert(
        'kill -0 "$old_dedupe_pid"' in installer,
        "Dedupe handoff lacks PID deduplication",
    )
    _assert(
        '"${PREFIX:-}" == *com.termux*' in installer,
        "Dedupe physical handoff lacks Termux gate",
    )

    forbidden = (
        "eval ",
        "exec ",
        "bash -c",
        "adb reboot",
        "curl | bash",
        "curl|bash",
        "wget | bash",
        "wget|bash",
    )
    lowered = (recovery + "\n" + installer).lower()
    for token in forbidden:
        _assert(token not in lowered, f"unsafe authority token present: {token}")

    return {
        "shell_syntax": "PASS",
        "trusted_source_binding": "PASS",
        "controller_pid_dedup": "PASS",
        "boot_watchdog_dedup": "PASS",
        "source_refresh": "PASS",
        "physical_gate_preserved": "PASS",
        "unsafe_authority_scan": "PASS",
    }


def _host_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(base / "home"),
                "CENTINAL26_ROOT": str(base / "missing-repo"),
                "AUTOMATION_BRIDGE_ROOT": str(base / "bridge"),
                "FROST_WORKER_RECOVERY_STATE": str(base / "state"),
            }
        )
        env.pop("PREFIX", None)
        result = _run(["bash", str(RECOVERY), "--once"], env=env)
        _assert(
            result.returncode == 40,
            f"non-Termux execution did not fail closed: rc={result.returncode}",
        )
        _assert(
            _status(base / "state").get("state") == "NOT_TERMUX",
            "non-Termux status was not explicit",
        )


def _write_fixture_repo(repo: Path) -> Path:
    bootstrap = repo / "deploy" / "termux" / "FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh"
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT=\"${AUTOMATION_BRIDGE_ROOT:?}\"
COUNT=\"${FROST_FIXTURE_BOOTSTRAP_COUNT:?}\"
mkdir -p \"$ROOT/bin\" \"$ROOT/state\"
printf '1\\n' >> \"$COUNT\"
printf 'configured=1\\n' > \"$ROOT/bridge.env\"
cat > \"$ROOT/bin/fleet-worker-start\" <<'WORKER'
#!/usr/bin/env bash
set -euo pipefail
ROOT=\"${AUTOMATION_BRIDGE_ROOT:?}\"
PIDFILE=\"$ROOT/state/fleet_worker.pid\"
mkdir -p \"$ROOT/state\"
if [[ -f \"$PIDFILE\" ]]; then
  old=\"$(cat \"$PIDFILE\" 2>/dev/null || true)\"
  if [[ -n \"$old\" ]] && kill -0 \"$old\" 2>/dev/null; then
    exit 0
  fi
fi
nohup sleep 300 >/dev/null 2>&1 &
echo $! > \"$PIDFILE\"
WORKER
chmod 700 \"$ROOT/bin/fleet-worker-start\"
\"$ROOT/bin/fleet-worker-start\"
""",
        encoding="utf-8",
    )
    bootstrap.chmod(0o700)
    for argv in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "verifier@example.invalid"],
        ["git", "config", "user.name", "G02 verifier"],
        ["git", "add", "."],
        ["git", "commit", "-qm", "fixture"],
    ):
        result = _run(argv, cwd=repo)
        _assert(
            result.returncode == 0,
            f"fixture git command failed: {argv}: {result.stderr}",
        )
    return bootstrap


def _black_box_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home = base / "home"
        repo = base / "repo"
        bridge = base / "bridge"
        state = base / "state"
        count = base / "bootstrap-count.txt"
        home.mkdir()
        repo.mkdir()
        bootstrap = _write_fixture_repo(repo)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "PREFIX": "/data/data/com.termux/files/usr",
                "CENTINAL26_ROOT": str(repo),
                "AUTOMATION_BRIDGE_ROOT": str(bridge),
                "FROST_WORKER_RECOVERY_STATE": str(state),
                "FROST_FIXTURE_BOOTSTRAP_COUNT": str(count),
                "BASE44_TOKEN": "fixture-token",
                "BASE44_WORKER_EMAIL": "worker@example.invalid",
            }
        )
        pid = None
        try:
            first = _run(["bash", str(RECOVERY), "--install"], env=env)
            _assert(
                first.returncode == 0,
                f"initial bounded recovery failed: rc={first.returncode} stderr={first.stderr}",
            )
            pid = _pid(bridge)
            _assert(
                _status(state).get("state") == "RECOVERED",
                "initial worker recovery was not recorded",
            )
            _assert(
                count.read_text().splitlines() == ["1"],
                "bootstrap was not invoked exactly once",
            )
            hook = home / ".termux" / "boot" / "frost-android-worker-self-recovery.sh"
            _assert(
                hook.is_file() and "pgrep -f" in hook.read_text(),
                "boot-persistent duplicate guard was not installed",
            )

            second = _run(["bash", str(RECOVERY), "--once"], env=env)
            _assert(
                second.returncode == 0,
                f"healthy-worker observation failed: rc={second.returncode}",
            )
            _assert(_pid(bridge) == pid, "healthy worker was duplicated")
            _assert(
                _status(state).get("state") == "RUNNING",
                "healthy worker state was not recorded",
            )
            _assert(
                count.read_text().splitlines() == ["1"],
                "healthy worker triggered an unnecessary reinstall",
            )

            _terminate(pid)
            pid = None
            (bridge / "state" / "fleet_worker.pid").unlink(missing_ok=True)
            third = _run(["bash", str(RECOVERY), "--once"], env=env)
            _assert(
                third.returncode == 0,
                f"existing-worker restart failed: rc={third.returncode}",
            )
            pid = _pid(bridge)
            _assert(
                _status(state).get("state") == "RECOVERED",
                "existing worker restart was not recorded",
            )
            _assert(
                count.read_text().splitlines() == ["1"],
                "existing worker restart unnecessarily reran bootstrap",
            )

            _terminate(pid)
            pid = None
            shutil.rmtree(bridge)
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8") + "\n# tamper\n",
                encoding="utf-8",
            )
            fourth = _run(["bash", str(RECOVERY), "--once"], env=env)
            _assert(
                fourth.returncode == 31,
                f"tampered source failure code was not preserved: rc={fourth.returncode}",
            )
            _assert(
                _status(state).get("state") == "SOURCE_UNTRUSTED",
                "tampered source was not rejected",
            )
        finally:
            if pid is not None:
                _terminate(pid)


def verify() -> dict[str, object]:
    static = _static_contract()
    _host_fail_closed()
    _black_box_recovery()
    return {
        "schema": "g02-independent-verification/v1",
        "verdict": "VERIFIED",
        "scope": "host-verifiable persistence and bounded self-recovery semantics",
        "criteria": {
            "restart_safe_persistence": "PASS",
            "self_refresh": "PASS",
            "bounded_recovery": "PASS",
            "deduplicated_controllers": "PASS",
            "trusted_source_fail_closed": "PASS",
            "non_termux_fail_closed": "PASS",
            **static,
        },
        "limits": [
            "does not establish Android device execution",
            "does not establish reboot persistence on a physical handset",
            "does not establish Base44 credential availability",
            "does not establish DEVICE_VALIDATED or PERSISTENT_VALIDATED",
        ],
    }


def main() -> int:
    try:
        result = verify()
    except (
        VerificationFailure,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema": "g02-independent-verification/v1",
                    "verdict": "FAIL",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
