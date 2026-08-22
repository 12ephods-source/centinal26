import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import time
import uuid
from dataclasses import dataclass

SCHEMA = 4
QUALIFIED = (
    "repo_sync",
    "repo_clean",
    "pair_ok",
    "skynet_ok",
    "device_boot_ok",
    "device_restart_ok",
    "device_exec_ok",
    "device_audit_ok",
    "state_integrity_ok",
    "recovery_ok",
    "security_policy_ok",
)


def _load_security():
    path = pathlib.Path(__file__).with_name("security.py")
    spec = importlib.util.spec_from_file_location("persistent_security", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECURITY = _load_security()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: pathlib.Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@dataclass
class Kernel:
    root: pathlib.Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.state = self.root / "project_state.json"
        self.ledger = self.root / "evidence.jsonl"
        self.marker = self.root / "PROJECT_GOAL_REACHED"

    def load(self):
        if not self.state.exists():
            return {
                "schema": SCHEMA,
                "release": None,
                "status": "UNQUALIFIED",
                "generation": 0,
                "checks": {key: False for key in QUALIFIED},
                "metrics": {"cycles": 0, "recoveries": 0, "demotions": 0},
                "last_event_hash": None,
                "security": {"allowed": False, "reasons": ["not_evaluated"]},
            }
        obj = json.loads(self.state.read_text())
        if obj.get("schema") != SCHEMA:
            raise RuntimeError("unsupported state schema")
        return obj

    def append_event(self, event):
        prev = None
        if self.ledger.exists():
            lines = self.ledger.read_text().splitlines()
            if lines:
                prev = json.loads(lines[-1])["event_hash"]
        body = {
            "schema": SCHEMA,
            "event_id": str(uuid.uuid4()),
            "time_utc": now(),
            "prev_event_hash": prev,
            **event,
        }
        body["event_hash"] = sha(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
        with self.ledger.open("a") as handle:
            handle.write(json.dumps(body, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return body["event_hash"]

    def commit(
        self,
        release,
        checks,
        detail="",
        worker="kernel",
        inputs=None,
        security_context=None,
    ):
        old = self.load()
        security = SECURITY.SecurityPolicy().evaluate(security_context or {})
        normalized = {key: bool(checks.get(key, False)) for key in QUALIFIED}
        normalized["security_policy_ok"] = security.allowed
        goal = all(normalized.values())
        old_goal = old.get("status") == "PROJECT_GOAL_REACHED"
        metrics = dict(old.get("metrics", {}))
        metrics["cycles"] = int(metrics.get("cycles", 0)) + 1
        if old_goal and not goal:
            metrics["demotions"] = int(metrics.get("demotions", 0)) + 1
        if detail.startswith("recovered:"):
            metrics["recoveries"] = int(metrics.get("recoveries", 0)) + 1
        status = "PROJECT_GOAL_REACHED" if goal else (
            "DEMOTED" if old_goal else "UNQUALIFIED"
        )
        security_record = {
            "allowed": security.allowed,
            "checks": security.checks,
            "reasons": list(security.reasons),
            "context_hash": security.context_hash,
        }
        event_hash = self.append_event(
            {
                "type": "qualification",
                "release": release,
                "worker": worker,
                "inputs": inputs or {},
                "checks": normalized,
                "security": security_record,
                "status": status,
                "detail": detail,
            }
        )
        obj = {
            "schema": SCHEMA,
            "release": release,
            "status": status,
            "goal_reached": goal,
            "generation": int(old.get("generation", 0)) + 1,
            "updated_at_utc": now(),
            "checks": normalized,
            "security": security_record,
            "metrics": metrics,
            "last_event_hash": event_hash,
        }
        payload = (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode()
        atomic_write(self.state, payload)
        atomic_write(
            pathlib.Path(str(self.state) + ".sha256"),
            (sha(payload) + "  " + self.state.name + "\n").encode(),
        )
        if goal:
            atomic_write(
                self.marker,
                (release + " " + obj["updated_at_utc"] + " " + event_hash + "\n").encode(),
            )
        elif self.marker.exists():
            self.marker.unlink()
        return obj

    def verify(self):
        obj = self.load()
        problems = []
        if self.state.exists():
            side = pathlib.Path(str(self.state) + ".sha256")
            if not side.exists() or side.read_text().split()[0] != sha(
                self.state.read_bytes()
            ):
                problems.append("state_hash")
        prev = None
        if self.ledger.exists():
            for number, line in enumerate(self.ledger.read_text().splitlines(), 1):
                event = json.loads(line)
                event_hash = event.pop("event_hash")
                if event.get("prev_event_hash") != prev:
                    problems.append(f"ledger_chain:{number}")
                if sha(
                    json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
                ) != event_hash:
                    problems.append(f"ledger_hash:{number}")
                prev = event_hash
        if obj.get("last_event_hash") != prev and self.ledger.exists():
            problems.append("state_ledger_head")
        if obj.get("goal_reached") != all(
            obj.get("checks", {}).get(key, False) for key in QUALIFIED
        ):
            problems.append("goal_logic")
        if obj.get("goal_reached") != self.marker.exists():
            problems.append("goal_marker")
        if obj.get("checks", {}).get("security_policy_ok") != obj.get("security", {}).get("allowed"):
            problems.append("security_logic")
        return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state", default=os.path.expanduser("~/.frost_persistent_v4")
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    commit_parser = sub.add_parser("commit")
    commit_parser.add_argument("--release", required=True)
    commit_parser.add_argument("--checks-json", required=True)
    commit_parser.add_argument("--detail", default="")
    commit_parser.add_argument("--worker", default="kernel")
    commit_parser.add_argument("--inputs-json", default="{}")
    commit_parser.add_argument("--security-context-json", default="{}")
    sub.add_parser("verify")
    sub.add_parser("status")
    args = parser.parse_args()
    kernel = Kernel(pathlib.Path(args.state))
    if args.cmd == "commit":
        print(
            json.dumps(
                kernel.commit(
                    args.release,
                    json.loads(args.checks_json),
                    args.detail,
                    args.worker,
                    json.loads(args.inputs_json),
                    json.loads(args.security_context_json),
                ),
                sort_keys=True,
            )
        )
    elif args.cmd == "verify":
        problems = kernel.verify()
        print(json.dumps({"ok": not problems, "problems": problems}))
        raise SystemExit(0 if not problems else 1)
    else:
        print(json.dumps(kernel.load(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
