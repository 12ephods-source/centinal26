from __future__ import annotations

import hashlib
import json
import os
import selectors
import shutil
import signal
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SandboxUnavailable(RuntimeError):
    """Raised when the hard isolation boundary cannot be created."""


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 5
    memory_bytes: int = 256 * 1024 * 1024
    processes: int = 32
    wall_seconds: float = 10.0
    output_bytes: int = 1024 * 1024
    open_files: int = 64
    cpus: float = 1.0
    tmp_bytes: int = 64 * 1024 * 1024

    def validate(self) -> None:
        if self.cpu_seconds < 1:
            raise ValueError("cpu_seconds must be positive")
        if self.memory_bytes < 32 * 1024 * 1024:
            raise ValueError("memory_bytes must be at least 32 MiB")
        if self.processes < 1:
            raise ValueError("processes must be positive")
        if self.wall_seconds <= 0:
            raise ValueError("wall_seconds must be positive")
        if self.output_bytes < 1:
            raise ValueError("output_bytes must be positive")
        if self.open_files < 8:
            raise ValueError("open_files must be at least 8")
        if not 0 < self.cpus <= 8:
            raise ValueError("cpus must be in (0, 8]")
        if self.tmp_bytes < 1024 * 1024:
            raise ValueError("tmp_bytes must be at least 1 MiB")


@dataclass(frozen=True)
class SandboxResult:
    schema_version: int
    sandbox_backend: str
    sandbox_image_id: str
    candidate_commit: str
    goal_digest: str
    source_digest: str
    validator_versions: dict[str, str]
    command: list[str]
    limits: dict[str, Any]
    isolation: dict[str, Any]
    exit_code: int | None
    timed_out: bool
    output_limited: bool
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str
    started_at: str
    duration_seconds: float
    evidence_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _tree_digest(root: Path) -> str:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        stat_result = path.lstat()
        if path.is_symlink():
            entries.append(
                {
                    "path": relative,
                    "type": "symlink",
                    "target": os.readlink(path),
                    "mode": stat_result.st_mode & 0o777,
                }
            )
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "sha256": _sha256_bytes(path.read_bytes()),
                    "mode": stat_result.st_mode & 0o777,
                }
            )
        elif path.is_dir():
            entries.append(
                {
                    "path": relative,
                    "type": "directory",
                    "mode": stat_result.st_mode & 0o777,
                }
            )
        else:
            raise ValueError(f"unsupported candidate filesystem entry: {relative}")
    return _sha256_json(entries)


def _validate_hex_digest(value: str, name: str, lengths: set[int]) -> None:
    if len(value) not in lengths or any(character not in "0123456789abcdef" for character in value):
        allowed = ", ".join(str(length) for length in sorted(lengths))
        raise ValueError(f"{name} must be lowercase hex with length {allowed}")


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _bounded_communicate(
    process: subprocess.Popen[bytes], *, wall_seconds: float, output_bytes: int
) -> tuple[bytes, bytes, bool, bool]:
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("sandbox output pipes were not created")

    selector = selectors.DefaultSelector()
    streams = {process.stdout.fileno(): "stdout", process.stderr.fileno(): "stderr"}
    for file_descriptor in streams:
        os.set_blocking(file_descriptor, False)
        selector.register(file_descriptor, selectors.EVENT_READ)

    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    timed_out = False
    output_limited = False
    deadline = time.monotonic() + wall_seconds

    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0 and process.poll() is None:
            timed_out = True
            _kill_process_group(process)
            remaining = 0.1

        events = selector.select(timeout=max(0.0, min(0.1, remaining)))
        if not events and process.poll() is not None:
            events = [(key, selectors.EVENT_READ) for key in selector.get_map().values()]

        for key, _mask in events:
            file_descriptor = int(key.fd)
            try:
                chunk = os.read(file_descriptor, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(file_descriptor)
                continue
            allowed = max(0, output_bytes - total)
            if allowed:
                kept = chunk[:allowed]
                buffers[streams[file_descriptor]].extend(kept)
                total += len(kept)
            if len(chunk) > allowed:
                output_limited = True
                _kill_process_group(process)

        if output_limited and process.poll() is None:
            _kill_process_group(process)

    process.wait(timeout=1)
    return bytes(buffers["stdout"]), bytes(buffers["stderr"]), timed_out, output_limited


class DockerEvaluator:
    """Ephemeral Docker evaluator with no host-execution fallback."""

    def __init__(self, docker_binary: str | Path | None = None, image: str | None = None):
        discovered = shutil.which("docker") if docker_binary is None else str(docker_binary)
        self.docker = None if discovered is None else Path(discovered)
        self.image = image or os.environ.get(
            "CENTINAL26_SANDBOX_IMAGE", "centinal26-sandbox-root:local"
        )

    def _require_docker(self) -> Path:
        if self.docker is None or not self.docker.is_file():
            raise SandboxUnavailable("docker is unavailable")
        return self.docker

    def _run_docker_control(self, arguments: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[bytes]:
        docker = self._require_docker()
        return subprocess.run(
            [str(docker), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env={},
            check=False,
            timeout=timeout,
        )

    def image_id(self) -> str:
        result = self._run_docker_control(
            ["image", "inspect", "--format", "{{.Id}}", self.image]
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace")[:400]
            raise SandboxUnavailable(f"sandbox image is unavailable: {detail}")
        image_id = result.stdout.decode("utf-8", errors="replace").strip()
        if not image_id.startswith("sha256:"):
            raise SandboxUnavailable("sandbox image did not resolve to a content identity")
        return image_id

    def _mount_arguments(self, candidate_root: Path) -> list[str]:
        mounts: list[tuple[Path, str]] = [(candidate_root, "/src"), (Path("/usr"), "/usr")]
        for host_path in (Path("/lib"), Path("/lib64"), Path("/bin")):
            if host_path.exists():
                mounts.append((host_path, str(host_path)))
        arguments: list[str] = []
        for source, destination in mounts:
            source_text = str(source)
            if "," in source_text:
                raise ValueError("sandbox source paths may not contain commas")
            arguments.extend(
                [
                    "--mount",
                    f"type=bind,src={source_text},dst={destination},readonly",
                ]
            )
        return arguments

    def _base_command(
        self, candidate_root: Path, limits: SandboxLimits, container_name: str
    ) -> list[str]:
        docker = self._require_docker()
        command = [
            str(docker),
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--ipc",
            "private",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--user",
            "65534:65534",
            "--pids-limit",
            str(limits.processes),
            "--memory",
            str(limits.memory_bytes),
            "--memory-swap",
            str(limits.memory_bytes),
            "--cpus",
            str(limits.cpus),
            "--ulimit",
            f"cpu={limits.cpu_seconds}:{limits.cpu_seconds + 1}",
            "--ulimit",
            f"nproc={limits.processes}:{limits.processes}",
            "--ulimit",
            f"nofile={limits.open_files}:{limits.open_files}",
            "--ulimit",
            "core=0:0",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={limits.tmp_bytes}",
            "--workdir",
            "/src",
            "--hostname",
            "centinal26-sandbox",
            "--env",
            "PATH=/usr/bin:/bin",
            "--env",
            "HOME=/nonexistent",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            *self._mount_arguments(candidate_root),
            self.image,
        ]
        return command

    def _force_remove(self, container_name: str) -> None:
        try:
            self._run_docker_control(["rm", "-f", container_name], timeout=5)
        except (OSError, subprocess.SubprocessError):
            return

    def probe(self) -> None:
        self.image_id()
        probe_root = Path("/usr").resolve()
        limits = SandboxLimits(cpu_seconds=2, wall_seconds=3, memory_bytes=128 * 1024 * 1024)
        container_name = f"centinal26-probe-{uuid.uuid4().hex[:16]}"
        command = self._base_command(probe_root, limits, container_name) + ["/usr/bin/true"]
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env={},
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            self._force_remove(container_name)
            detail = result.stderr.decode("utf-8", errors="replace")[:400]
            raise SandboxUnavailable(f"docker isolation probe failed: {detail}")

    def evaluate(
        self,
        candidate_root: Path,
        *,
        candidate_commit: str,
        goal_digest: str,
        command: list[str],
        validator_versions: dict[str, str],
        limits: SandboxLimits | None = None,
    ) -> SandboxResult:
        limits = limits or SandboxLimits()
        limits.validate()
        _validate_hex_digest(candidate_commit, "candidate_commit", {40, 64})
        _validate_hex_digest(goal_digest, "goal_digest", {64})
        if not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError("command must contain one or more non-empty strings")
        if not validator_versions or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in validator_versions.items()
        ):
            raise ValueError("validator_versions must be a non-empty string mapping")

        candidate_root = candidate_root.expanduser().resolve(strict=True)
        if not candidate_root.is_dir():
            raise NotADirectoryError(candidate_root)
        source_digest = _tree_digest(candidate_root)

        self.probe()
        image_id = self.image_id()
        container_name = f"centinal26-eval-{uuid.uuid4().hex[:16]}"
        docker_command = self._base_command(candidate_root, limits, container_name) + command
        started_at = datetime.now(UTC).isoformat()
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                docker_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={},
                cwd="/",
                start_new_session=True,
            )
        except OSError as error:
            raise SandboxUnavailable(f"could not create Docker sandbox: {error}") from error

        try:
            stdout, stderr, timed_out, output_limited = _bounded_communicate(
                process,
                wall_seconds=limits.wall_seconds,
                output_bytes=limits.output_bytes,
            )
        finally:
            self._force_remove(container_name)
        duration = time.monotonic() - started

        body: dict[str, Any] = {
            "schema_version": 1,
            "sandbox_backend": "docker",
            "sandbox_image_id": image_id,
            "candidate_commit": candidate_commit,
            "goal_digest": goal_digest,
            "source_digest": source_digest,
            "validator_versions": dict(sorted(validator_versions.items())),
            "command": list(command),
            "limits": asdict(limits),
            "isolation": {
                "network": "none",
                "pid_namespace": "private",
                "ipc_namespace": "private",
                "source_mount": "read_only",
                "root_filesystem": "read_only",
                "home_mount": "absent",
                "environment": "explicit_minimal",
                "device_mounts": "docker_default_minimal",
                "capabilities": "all_dropped",
                "no_new_privileges": True,
                "docker_socket_mounted": False,
                "ssh_agent_mounted": False,
                "host_execution_fallback": False,
                "seccomp": "docker_default",
                "resource_limits": "cgroup_plus_ulimit",
            },
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "output_limited": output_limited,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stdout_sha256": _sha256_bytes(stdout),
            "stderr_sha256": _sha256_bytes(stderr),
            "started_at": started_at,
            "duration_seconds": duration,
        }
        body["evidence_sha256"] = _sha256_json(body)
        return SandboxResult(**body)


def verify_result_hash(result: SandboxResult | dict[str, Any]) -> bool:
    body = result.as_dict() if isinstance(result, SandboxResult) else dict(result)
    found = body.pop("evidence_sha256", None)
    return isinstance(found, str) and found == _sha256_json(body)
