from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/12ephods-source/centinal26.git"
QUALIFIED_DEVICE_SOURCE = "9c0925ee7e3dc23f6e81718f9c1a2ca7926ec483"
DEFAULT_STATE_ROOT = Path.home() / ".local" / "share" / "frost-evidence-gate"


class EvidenceGateError(RuntimeError):
    """Evidence collection failed without promoting the affected gate."""


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceGateError(f"expected JSON object: {path}")
    return value


def run_checked(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 300,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=capture,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise EvidenceGateError(f"command unavailable or timed out: {args[0]}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        command = " ".join(args)
        raise EvidenceGateError(
            f"command failed ({completed.returncode}): {command}: {detail}"
        )
    return completed


def require_tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise EvidenceGateError(f"required tool unavailable: {name}")
    return resolved


def android_termux_observed() -> bool:
    prefix = os.environ.get("PREFIX", "")
    return bool(os.environ.get("ANDROID_ROOT") and "com.termux" in prefix)


def read_boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    try:
        value = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise EvidenceGateError("boot_id is not readable") from exc
    if not value:
        raise EvidenceGateError("boot_id is empty")
    return value


def getprop(name: str) -> str:
    try:
        completed = subprocess.run(
            ["getprop", name],
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


def default_device_id() -> str:
    serial = getprop("ro.serialno")
    if serial and serial != "unknown":
        return serial
    manufacturer = getprop("ro.product.manufacturer") or "android"
    model = getprop("ro.product.model") or "device"
    return f"{manufacturer}-{model}-{utc_stamp()}"


def ensure_source_checkout(state_root: Path, commit: str) -> Path:
    require_tool("git")
    if len(commit) != 40 or any(
        ch not in "0123456789abcdefABCDEF" for ch in commit
    ):
        raise EvidenceGateError("source commit must be a full 40-character SHA")
    checkout = state_root / "source" / commit
    if not (checkout / ".git").is_dir():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run_checked(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                REPO_URL,
                str(checkout),
            ],
            timeout=600,
        )
    run_checked(
        ["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", commit],
        timeout=600,
    )
    run_checked(
        ["git", "-C", str(checkout), "checkout", "--detach", "--force", commit]
    )
    actual = run_checked(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"]
    ).stdout.strip()
    if actual.lower() != commit.lower():
        raise EvidenceGateError(f"source checkout mismatch: {actual}")
    return checkout


def make_zip(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise EvidenceGateError(
                    f"symlink rejected from evidence package: {path}"
                )
            if path.is_file():
                arcname = f"{root.name}/{path.relative_to(root).as_posix()}"
                archive.write(path, arcname=arcname)
    temporary.replace(output)


def commission(state_root: Path, *, device_id: str | None = None) -> dict[str, Any]:
    if not android_termux_observed():
        raise EvidenceGateError("physical commissioning must run inside Android/Termux")
    require_tool("python")
    source = ensure_source_checkout(state_root, QUALIFIED_DEVICE_SOURCE)
    device_id = device_id or default_device_id()
    session = state_root / "sessions" / f"commissioning_{utc_stamp()}"
    bundle_root = session / "bundle"
    bundle_root.parent.mkdir(parents=True, exist_ok=True)

    package_dir = source / "automation" / "deployment" / "enrollment_package"
    capture = package_dir / "capture_device_evidence.py"
    heartbeat = source / "automation" / "device" / "heartbeat.py"
    verifier = package_dir / "verify_physical_commissioning.py"

    run_checked(
        [
            sys.executable,
            str(capture),
            "--device-id",
            device_id,
            "--source-commit",
            QUALIFIED_DEVICE_SOURCE,
            "--output",
            str(bundle_root),
        ],
        cwd=source,
        timeout=600,
    )
    manifest_path = bundle_root / "MANIFEST.sha256.json"
    if not manifest_path.is_file():
        raise EvidenceGateError("commissioning manifest missing")
    enrollment_digest = sha256_file(manifest_path)
    run_checked(
        [
            sys.executable,
            str(heartbeat),
            "--device-id",
            device_id,
            "--enrollment-digest",
            enrollment_digest,
            "--sequence",
            "1",
            "--output",
            str(bundle_root / "worker_heartbeat.json"),
        ],
        cwd=source,
    )

    package = session / f"guardian_physical_validation_{utc_stamp()}.zip"
    make_zip(bundle_root, package)
    verified = run_checked(
        [
            sys.executable,
            str(verifier),
            str(package),
            "--expected-source-commit",
            QUALIFIED_DEVICE_SOURCE,
        ],
        cwd=source,
        timeout=300,
    )
    verification = json.loads(verified.stdout)
    if verification.get("status") != "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE":
        raise EvidenceGateError(
            "commissioning verifier did not return eligible status"
        )

    enrollment = verification.get("enrollment") or {}
    receipt = {
        "schema": "frost.evidence_gate.commissioning.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "qualified_source_commit": QUALIFIED_DEVICE_SOURCE,
        "device_id": device_id,
        "boot_id": enrollment.get("boot_id") or read_boot_id(),
        "enrollment_digest": enrollment_digest,
        "package_path": str(package),
        "package_sha256": sha256_file(package),
        "verification": verification,
        "device_validated": False,
        "reason": (
            "Commissioning eligibility alone does not satisfy bounded-work and "
            "independent-evidence requirements."
        ),
    }
    write_json(session / "commissioning_receipt.json", receipt)
    write_json(state_root / "current_commissioning.json", receipt)
    return receipt


def worker_once(state_root: Path, config_path: Path) -> dict[str, Any]:
    if not android_termux_observed():
        raise EvidenceGateError("bounded worker execution must run inside Android/Termux")
    current = read_json(state_root / "current_commissioning.json")
    source_commit = str(current["qualified_source_commit"])
    source = ensure_source_checkout(state_root, source_commit)
    worker = source / "automation" / "device" / "outbound_worker.py"
    completed = run_checked(
        [
            sys.executable,
            str(worker),
            "--config",
            str(config_path.expanduser()),
            "--once",
        ],
        cwd=source,
        timeout=180,
    )
    worker_config = read_json(config_path.expanduser())
    worker_state = Path(str(worker_config["state_dir"])).expanduser()
    journal = worker_state / "journal.jsonl"
    receipt = {
        "schema": "frost.evidence_gate.worker_once.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "result": completed.stdout.strip(),
        "worker_config_path": str(config_path.expanduser()),
        "journal_path": str(journal),
        "journal_sha256": sha256_file(journal) if journal.is_file() else None,
        "bounded_work_observed": completed.stdout.strip() == "PASS",
        "independent_judge_verified": False,
    }
    write_json(state_root / "worker_once_receipt.json", receipt)
    return receipt


def derive_age_recipient(identity: Path) -> str:
    require_tool("age-keygen")
    if not identity.is_file() or identity.is_symlink():
        raise EvidenceGateError("age identity must be a regular local file")
    completed = run_checked(["age-keygen", "-y", str(identity)])
    recipient = completed.stdout.strip()
    if not recipient.startswith("age1"):
        raise EvidenceGateError("age-keygen did not derive a native age recipient")
    return recipient


def init_age_identity(state_root: Path, identity: Path | None = None) -> dict[str, Any]:
    age_keygen = require_tool("age-keygen")
    identity = (
        identity.expanduser()
        if identity is not None
        else state_root / "keys" / "age-identity.txt"
    )
    identity.parent.mkdir(parents=True, exist_ok=True)
    if identity.exists():
        if not identity.is_file() or identity.is_symlink():
            raise EvidenceGateError("existing age identity is not a regular file")
    else:
        run_checked([age_keygen, "-o", str(identity)])
        os.chmod(identity, 0o600)
    recipient = derive_age_recipient(identity)
    result = {
        "schema": "frost.evidence_gate.age_identity.v1",
        "identity_path": str(identity),
        "recipient": recipient,
        "private_key_exported": False,
    }
    write_json(state_root / "age_identity_receipt.json", result)
    return result


def offdevice_roundtrip(
    state_root: Path,
    *,
    source: Path,
    identity: Path,
    remote_target: str,
) -> dict[str, Any]:
    age = require_tool("age")
    rclone = require_tool("rclone")
    source = source.expanduser()
    identity = identity.expanduser()
    if not source.is_file() or source.is_symlink():
        raise EvidenceGateError(
            "round-trip source must be a regular non-symlink file"
        )
    if not remote_target.strip() or ":" not in remote_target:
        raise EvidenceGateError(
            "remote target must be an rclone remote path such as remote:path"
        )
    recipient = derive_age_recipient(identity)
    session = state_root / "sessions" / f"offdevice_{utc_stamp()}"
    session.mkdir(parents=True, exist_ok=True)
    ciphertext = session / f"{source.name}.age"
    recovered_ciphertext = session / f"recovered-{source.name}.age"
    recovered_plaintext = session / f"recovered-{source.name}"
    remote_object = remote_target.rstrip("/") + "/" + ciphertext.name

    run_checked(
        [
            age,
            "--encrypt",
            "--recipient",
            recipient,
            "--output",
            str(ciphertext),
            str(source),
        ],
        timeout=600,
    )
    source_hash = sha256_file(source)
    ciphertext_hash = sha256_file(ciphertext)

    run_checked(
        [rclone, "copyto", str(ciphertext), remote_object],
        timeout=1200,
    )
    run_checked(
        [rclone, "copyto", remote_object, str(recovered_ciphertext)],
        timeout=1200,
    )
    recovered_ciphertext_hash = sha256_file(recovered_ciphertext)
    if recovered_ciphertext_hash != ciphertext_hash:
        raise EvidenceGateError("retrieved ciphertext hash mismatch")

    run_checked(
        [
            age,
            "--decrypt",
            "--identity",
            str(identity),
            "--output",
            str(recovered_plaintext),
            str(recovered_ciphertext),
        ],
        timeout=600,
    )
    recovered_plaintext_hash = sha256_file(recovered_plaintext)
    if recovered_plaintext_hash != source_hash:
        raise EvidenceGateError("recovered plaintext hash mismatch")

    receipt = {
        "schema": "frost.evidence_gate.offdevice_roundtrip.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "provider": "age+rclone",
        "remote_target": remote_object,
        "source_path": str(source),
        "source_sha256": source_hash,
        "ciphertext_path": str(ciphertext),
        "ciphertext_sha256": ciphertext_hash,
        "recovered_ciphertext_sha256": recovered_ciphertext_hash,
        "recovered_plaintext_sha256": recovered_plaintext_hash,
        "age_recipient": recipient,
        "identity_path_recorded": False,
        "credentials_recorded": False,
        "remote_deletion_performed": False,
        "encrypted_artifact_verified": True,
        "off_device_roundtrip_verified": True,
        "recovery_verified": True,
    }
    write_json(session / "offdevice_roundtrip_receipt.json", receipt)
    write_json(state_root / "offdevice_roundtrip_receipt.json", receipt)
    return receipt


def reboot_evaluation(pre: dict[str, Any], current_boot_id: str) -> dict[str, Any]:
    before = str(pre.get("boot_id") or "")
    return {
        "pre_boot_id": before,
        "post_boot_id": current_boot_id,
        "boot_id_changed": bool(
            before and current_boot_id and before != current_boot_id
        ),
    }


def shell_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def arm_reboot(
    state_root: Path,
    *,
    worker_config: Path | None = None,
) -> dict[str, Any]:
    if not android_termux_observed():
        raise EvidenceGateError("reboot gate must be armed inside Android/Termux")
    current = read_json(state_root / "current_commissioning.json")
    pre = {
        "schema": "frost.evidence_gate.pre_reboot.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "boot_id": read_boot_id(),
        "device_id": current["device_id"],
        "enrollment_digest": current["enrollment_digest"],
        "qualified_source_commit": current["qualified_source_commit"],
        "commissioning_package_sha256": current["package_sha256"],
        "worker_config_path": (
            str(worker_config.expanduser()) if worker_config else None
        ),
    }
    write_json(state_root / "pre_reboot.json", pre)

    hook = Path.home() / ".termux" / "boot" / "frost-evidence-gate-resume"
    hook.parent.mkdir(parents=True, exist_ok=True)
    wrapper = Path.home() / "bin" / "frost-evidence-gate"
    hook.write_text(
        "#!/data/data/com.termux/files/usr/bin/bash\n"
        "sleep 20\n"
        f"{wrapper} post-reboot --state-root {shell_quote(str(state_root))} "
        f">>{shell_quote(str(state_root / 'post_reboot_boot.log'))} 2>&1\n",
        encoding="utf-8",
    )
    os.chmod(hook, 0o700)
    return {
        **pre,
        "boot_hook": str(hook),
        "physical_reboot_performed": False,
        "instruction": (
            "Use the device's physical reboot action. The collector does not "
            "initiate reboot."
        ),
    }


def post_reboot(state_root: Path) -> dict[str, Any]:
    if not android_termux_observed():
        raise EvidenceGateError("post-reboot capture must run inside Android/Termux")
    pre = read_json(state_root / "pre_reboot.json")
    current_boot_id = read_boot_id()
    evaluation = reboot_evaluation(pre, current_boot_id)
    if not evaluation["boot_id_changed"]:
        raise EvidenceGateError(
            "boot identity did not change; physical reboot evidence is not established"
        )
    source = ensure_source_checkout(
        state_root,
        str(pre["qualified_source_commit"]),
    )
    heartbeat_path = state_root / "post_reboot_heartbeat.json"
    heartbeat = source / "automation" / "device" / "heartbeat.py"
    verifier = source / "automation" / "device" / "verify_worker_heartbeat.py"
    run_checked(
        [
            sys.executable,
            str(heartbeat),
            "--device-id",
            str(pre["device_id"]),
            "--enrollment-digest",
            str(pre["enrollment_digest"]),
            "--sequence",
            "2",
            "--output",
            str(heartbeat_path),
        ],
        cwd=source,
    )
    verified = run_checked(
        [
            sys.executable,
            str(verifier),
            str(heartbeat_path),
            "--device-id",
            str(pre["device_id"]),
            "--enrollment-digest",
            str(pre["enrollment_digest"]),
            "--boot-id",
            current_boot_id,
        ],
        cwd=source,
    )
    heartbeat_verification = json.loads(verified.stdout)
    worker_receipt = None
    config_value = pre.get("worker_config_path")
    if isinstance(config_value, str) and config_value:
        try:
            worker_receipt = worker_once(state_root, Path(config_value))
        except EvidenceGateError as exc:
            worker_receipt = {
                "bounded_work_observed": False,
                "error": str(exc),
            }

    receipt = {
        "schema": "frost.evidence_gate.post_reboot.v1",
        "captured_at": datetime.now(UTC).isoformat(),
        **evaluation,
        "heartbeat_path": str(heartbeat_path),
        "heartbeat_sha256": sha256_file(heartbeat_path),
        "heartbeat_verification": heartbeat_verification,
        "worker_return_observed": heartbeat_verification.get("eligible") is True,
        "post_reboot_bounded_work": worker_receipt,
        "persistent_validated": False,
        "reason": (
            "Independent Judge and full event/lease-chain verification remain "
            "separate controller evidence."
        ),
    }
    write_json(state_root / "post_reboot_receipt.json", receipt)
    return receipt


def doctor(state_root: Path) -> dict[str, Any]:
    tools = {
        name: shutil.which(name)
        for name in ("git", "python", "age", "age-keygen", "rclone")
    }
    return {
        "schema": "frost.evidence_gate.doctor.v1",
        "android_termux_observed": android_termux_observed(),
        "boot_id_readable": Path("/proc/sys/kernel/random/boot_id").is_file(),
        "tools": {name: bool(path) for name, path in tools.items()},
        "state_root": str(state_root),
        "commissioning_receipt_present": (
            state_root / "current_commissioning.json"
        ).is_file(),
        "worker_receipt_present": (
            state_root / "worker_once_receipt.json"
        ).is_file(),
        "offdevice_roundtrip_receipt_present": (
            state_root / "offdevice_roundtrip_receipt.json"
        ).is_file(),
        "pre_reboot_present": (state_root / "pre_reboot.json").is_file(),
        "post_reboot_receipt_present": (
            state_root / "post_reboot_receipt.json"
        ).is_file(),
    }


def synthesize_status(state_root: Path) -> dict[str, Any]:
    commissioning = (
        read_json(state_root / "current_commissioning.json")
        if (state_root / "current_commissioning.json").is_file()
        else {}
    )
    worker = (
        read_json(state_root / "worker_once_receipt.json")
        if (state_root / "worker_once_receipt.json").is_file()
        else {}
    )
    offdevice = (
        read_json(state_root / "offdevice_roundtrip_receipt.json")
        if (state_root / "offdevice_roundtrip_receipt.json").is_file()
        else {}
    )
    post = (
        read_json(state_root / "post_reboot_receipt.json")
        if (state_root / "post_reboot_receipt.json").is_file()
        else {}
    )
    commissioning_ok = (
        commissioning.get("verification", {}).get("status")
        == "VERIFIED_PHYSICAL_COMMISSIONING_ELIGIBLE"
    )
    bounded_work_ok = worker.get("bounded_work_observed") is True
    recovery_ok = (
        offdevice.get("encrypted_artifact_verified") is True
        and offdevice.get("off_device_roundtrip_verified") is True
        and offdevice.get("recovery_verified") is True
    )
    post_work = post.get("post_reboot_bounded_work") or {}
    reboot_ok = (
        post.get("boot_id_changed") is True
        and post.get("worker_return_observed") is True
        and post_work.get("bounded_work_observed") is True
    )
    return {
        "schema": "frost.evidence_gate.status.v1",
        "commissioning_eligible": commissioning_ok,
        "bounded_work_observed": bounded_work_ok,
        "offdevice_recovery_verified": recovery_ok,
        "reboot_return_and_work_observed": reboot_ok,
        "device_validated_eligible": commissioning_ok and bounded_work_ok,
        "persistent_validated_eligible": (
            commissioning_ok and bounded_work_ok and reboot_ok
        ),
        "independent_judge_verified": False,
        "lease_event_chain_verified": False,
        "promotion_performed": False,
        "note": (
            "Eligibility remains subordinate to controller-side independent Judge "
            "and event/lease-chain evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect external evidence for Frost continuity/device gates."
    )
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")
    age_init = sub.add_parser("init-age")
    age_init.add_argument("--identity", type=Path)
    commission_parser = sub.add_parser("commission")
    commission_parser.add_argument("--device-id")
    worker_parser = sub.add_parser("worker-once")
    worker_parser.add_argument("--config", type=Path, required=True)
    recovery = sub.add_parser("offdevice-roundtrip")
    recovery.add_argument("--source", type=Path, required=True)
    recovery.add_argument("--identity", type=Path, required=True)
    recovery.add_argument("--remote", required=True)
    arm = sub.add_parser("arm-reboot")
    arm.add_argument("--worker-config", type=Path)
    sub.add_parser("post-reboot")
    sub.add_parser("status")

    args = parser.parse_args()
    state_root = args.state_root.expanduser()
    state_root.mkdir(parents=True, exist_ok=True)
    os.chmod(state_root, 0o700)

    try:
        if args.command == "doctor":
            result = doctor(state_root)
        elif args.command == "init-age":
            result = init_age_identity(state_root, args.identity)
        elif args.command == "commission":
            result = commission(state_root, device_id=args.device_id)
        elif args.command == "worker-once":
            result = worker_once(state_root, args.config)
        elif args.command == "offdevice-roundtrip":
            result = offdevice_roundtrip(
                state_root,
                source=args.source,
                identity=args.identity,
                remote_target=args.remote,
            )
        elif args.command == "arm-reboot":
            result = arm_reboot(state_root, worker_config=args.worker_config)
        elif args.command == "post-reboot":
            result = post_reboot(state_root)
        elif args.command == "status":
            result = synthesize_status(state_root)
        else:  # pragma: no cover
            raise AssertionError("unreachable")
    except (
        EvidenceGateError,
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
