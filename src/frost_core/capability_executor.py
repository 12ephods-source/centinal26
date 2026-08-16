from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Json = dict[str, Any]
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _provider_tool_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    # Provider function names are capped at 64 characters. The digest prevents
    # collisions introduced by replacing dots or other local separators.
    return f"frost_{safe[:49]}_{digest}"


def _scrubbed_env(allow_network: bool) -> dict[str, str]:
    keep = {
        "HOME",
        "PATH",
        "PREFIX",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "TERM",
        "ANDROID_ROOT",
        "ANDROID_DATA",
    }
    env = {key: value for key, value in os.environ.items() if key in keep}
    env.setdefault("PATH", os.environ.get("PATH", ""))
    if not allow_network:
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
        ):
            env.pop(key, None)
    return env


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    script_path: str
    script_sha256: str
    description: str
    timeout_seconds: int = 120
    max_args: int = 12
    max_arg_length: int = 512
    max_output_bytes: int = 200_000
    allow_network: bool = False
    enabled: bool = True

    @property
    def provider_tool_name(self) -> str:
        return _provider_tool_name(self.name)

    def tool_schema(self) -> Json:
        return {
            "type": "function",
            "name": self.provider_tool_name,
            "description": f"{self.description} Local capability: {self.name}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": self.max_arg_length},
                        "maxItems": self.max_args,
                    }
                },
                "required": ["args"],
                "additionalProperties": False,
            },
            "strict": True,
        }


class CapabilityRegistry:
    """Local, hash-pinned, named capability registry.

    Remote/model input can select only a registered name and bounded string arguments.
    The command path itself is established locally and is never supplied by the responder.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS capabilities (
                name TEXT PRIMARY KEY,
                script_path TEXT NOT NULL,
                script_sha256 TEXT NOT NULL,
                description TEXT NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                max_args INTEGER NOT NULL,
                max_arg_length INTEGER NOT NULL,
                max_output_bytes INTEGER NOT NULL,
                allow_network INTEGER NOT NULL,
                enabled INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capability_runs (
                call_id TEXT PRIMARY KEY,
                capability_name TEXT NOT NULL,
                args_json TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                result_sha256 TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def register(
        self,
        *,
        name: str,
        script_path: Path,
        description: str,
        timeout_seconds: int = 120,
        max_args: int = 12,
        max_arg_length: int = 512,
        max_output_bytes: int = 200_000,
        allow_network: bool = False,
    ) -> CapabilitySpec:
        if not _NAME_RE.fullmatch(name):
            raise ValueError("invalid capability name")
        script = script_path.expanduser().resolve()
        if not script.is_file():
            raise ValueError(f"capability script not found: {script}")
        if timeout_seconds < 1 or timeout_seconds > 3600:
            raise ValueError("timeout_seconds must be within 1..3600")
        if not 0 <= max_args <= 64:
            raise ValueError("max_args must be within 0..64")
        if not 1 <= max_arg_length <= 4096:
            raise ValueError("max_arg_length must be within 1..4096")
        if not 1024 <= max_output_bytes <= 2_000_000:
            raise ValueError("max_output_bytes must be within 1024..2000000")
        spec = CapabilitySpec(
            name=name,
            script_path=str(script),
            script_sha256=_sha256_file(script),
            description=description.strip() or name,
            timeout_seconds=timeout_seconds,
            max_args=max_args,
            max_arg_length=max_arg_length,
            max_output_bytes=max_output_bytes,
            allow_network=allow_network,
        )
        self.db.execute(
            """
            INSERT INTO capabilities(
                name,script_path,script_sha256,description,timeout_seconds,max_args,
                max_arg_length,max_output_bytes,allow_network,enabled
            ) VALUES(?,?,?,?,?,?,?,?,?,1)
            ON CONFLICT(name) DO UPDATE SET
                script_path=excluded.script_path,
                script_sha256=excluded.script_sha256,
                description=excluded.description,
                timeout_seconds=excluded.timeout_seconds,
                max_args=excluded.max_args,
                max_arg_length=excluded.max_arg_length,
                max_output_bytes=excluded.max_output_bytes,
                allow_network=excluded.allow_network,
                enabled=1
            """,
            (
                spec.name,
                spec.script_path,
                spec.script_sha256,
                spec.description,
                spec.timeout_seconds,
                spec.max_args,
                spec.max_arg_length,
                spec.max_output_bytes,
                int(spec.allow_network),
            ),
        )
        self.db.commit()
        return spec

    def list(self) -> list[CapabilitySpec]:
        rows = self.db.execute(
            "SELECT * FROM capabilities WHERE enabled=1 ORDER BY name"
        ).fetchall()
        return [self._spec(row) for row in rows]

    def tool_schemas(self) -> list[Json]:
        return [spec.tool_schema() for spec in self.list()]

    def execute(self, *, call_id: str, name: str, args: list[str]) -> Json:
        if not call_id.strip():
            raise ValueError("call_id must not be empty")
        row = self.db.execute(
            "SELECT * FROM capabilities WHERE name=? AND enabled=1", (name,)
        ).fetchone()
        if row is None:
            for candidate in self.db.execute(
                "SELECT * FROM capabilities WHERE enabled=1 ORDER BY name"
            ).fetchall():
                candidate_spec = self._spec(candidate)
                if candidate_spec.provider_tool_name == name:
                    row = candidate
                    break
        if row is None:
            raise PermissionError(f"capability is not registered/enabled: {name}")
        spec = self._spec(row)
        canonical_args = json.dumps(args, separators=(",", ":"), ensure_ascii=False)
        prior = self.db.execute(
            "SELECT capability_name,args_json,status,result_json FROM capability_runs WHERE call_id=?",
            (call_id,),
        ).fetchone()
        if prior is not None:
            if prior["capability_name"] != spec.name or prior["args_json"] != canonical_args:
                raise RuntimeError("call_id was reused for a different capability invocation")
            return json.loads(prior["result_json"])
        if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
            raise ValueError("capability args must be a list of strings")
        if len(args) > spec.max_args:
            raise ValueError("capability arg count exceeds local policy")
        if any(len(value) > spec.max_arg_length for value in args):
            raise ValueError("capability argument exceeds local policy")
        script = Path(spec.script_path)
        if not script.is_file():
            raise RuntimeError(f"registered capability script is missing: {script}")
        observed_hash = _sha256_file(script)
        if observed_hash != spec.script_sha256:
            raise PermissionError(
                f"registered capability hash changed: expected={spec.script_sha256} observed={observed_hash}"
            )

        started = time.time()
        status = "success"
        timed_out = False
        try:
            proc = subprocess.run(
                [str(script), *args],
                shell=False,
                cwd=str(script.parent),
                env=_scrubbed_env(spec.allow_network),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=spec.timeout_seconds,
                check=False,
            )
            stdout = proc.stdout[: spec.max_output_bytes]
            stderr = proc.stderr[: spec.max_output_bytes]
            exit_code = int(proc.returncode)
            if exit_code != 0:
                status = "failed"
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"")[: spec.max_output_bytes]
            stderr = (exc.stderr or b"")[: spec.max_output_bytes]
            exit_code = 124
            status = "timeout"
            timed_out = True

        result: Json = {
            "capability": spec.name,
            "status": status,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "script_sha256": spec.script_sha256,
        }
        body = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        finished = time.time()
        self.db.execute(
            """
            INSERT INTO capability_runs(
                call_id,capability_name,args_json,status,result_json,result_sha256,started_at,finished_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                call_id,
                spec.name,
                canonical_args,
                status,
                body,
                hashlib.sha256(body.encode("utf-8")).hexdigest(),
                started,
                finished,
            ),
        )
        self.db.commit()
        return result

    def status(self) -> Json:
        cap_count = self.db.execute(
            "SELECT COUNT(*) FROM capabilities WHERE enabled=1"
        ).fetchone()[0]
        run_count = self.db.execute("SELECT COUNT(*) FROM capability_runs").fetchone()[0]
        return {"enabled_capabilities": cap_count, "capability_runs": run_count}

    @staticmethod
    def _spec(row: sqlite3.Row) -> CapabilitySpec:
        data = dict(row)
        return CapabilitySpec(
            name=str(data["name"]),
            script_path=str(data["script_path"]),
            script_sha256=str(data["script_sha256"]),
            description=str(data["description"]),
            timeout_seconds=int(data["timeout_seconds"]),
            max_args=int(data["max_args"]),
            max_arg_length=int(data["max_arg_length"]),
            max_output_bytes=int(data["max_output_bytes"]),
            allow_network=bool(data["allow_network"]),
            enabled=bool(data["enabled"]),
        )
