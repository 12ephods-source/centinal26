"""FToE autonomous research daemon.

Scientific failures kill a branch, not the daemon. Missing external LLM credentials
remove that provider from the panel, not the research loop. Only an explicit STOP
file or process signal stops the daemon. Model responses are advisory: they never
execute shell commands or self-authorize repository mutations.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = pathlib.Path(
    os.environ.get(
        "FTOE_AUTOPILOT_STATE",
        str(pathlib.Path.home() / ".local/state/ftoe-autopilot"),
    )
)
STOP = STATE / "STOP"
AUDIT = STATE / "audit.jsonl"
CONFIG = ROOT / "physics/ftoe/agent_panel_config.json"
RUNNING = True

ALLOWLIST = [
    [sys.executable, "scripts/ftoe_so10_group_theory_gate.py"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_group_theory_gate", "-v"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_422_gate", "-v"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_uv_closure", "-v"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_threshold_stress", "-v"],
]


def utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def emit(kind: str, data: object) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    row = {"ts": utc(), "kind": kind, "data": data}
    row["sha256"] = hashlib.sha256(
        json.dumps(row, sort_keys=True).encode()
    ).hexdigest()
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def http_json(
    url: str,
    method: str = "GET",
    payload: object | None = None,
    token: str | None = None,
    timeout: int = 180,
) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def discover(cfg: dict) -> list[dict]:
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if not key:
        return []
    data = http_json(cfg["gateway_base_url"] + "/models", token=key).get("data", [])
    now = int(time.time())
    selected = []
    for provider in cfg["providers"]:
        candidates = [
            model
            for model in data
            if model.get("id", "").startswith(provider + "/")
            and model.get("type", "language") == "language"
            and (not model.get("released") or model["released"] <= now)
        ]

        def score(model: dict) -> float:
            tags = set(model.get("tags") or [])
            value = 8 * ("reasoning" in tags) + 3 * ("tool-use" in tags)
            value += min((model.get("context_window") or 0) / 250000, 4)
            value += (model.get("released") or 0) / 1e10
            return value

        candidates.sort(key=score, reverse=True)
        if candidates:
            selected.append(candidates[0])
    return selected[: cfg.get("max_models", 6)]


def context() -> str:
    files = [
        "docs/physics/FTOE_SO10_422_CLOSURE.md",
        "docs/physics/FTOE_SO10_UV_OPERATOR_AND_THRESHOLD_GATES.md",
        "physics/ftoe/uv_model_contract.json",
        "physics/ftoe/g422_spectrum_registry.json",
    ]
    out = []
    for rel in files:
        path = ROOT / rel
        if path.exists():
            out.append("\n--- " + rel + " ---\n" + path.read_text(errors="replace"))
    return "".join(out)[-60000:]


def ask(model: str, role: dict, ctx: str, cfg: dict) -> dict:
    key = os.environ.get("AI_GATEWAY_API_KEY")
    prompt = (
        "Falsification-first FToE research panel. Robert Frost is the manuscript author. "
        "Treat model output as advisory, distinguish verified/derived/proposed/failed, "
        "and never declare publication readiness without the repository gates. "
        "Return JSON with verdict,strongest_finding,failed_gates,next_gate,"
        "publication_blocker,proposed_patch.\nROLE="
        + role["name"]
        + "\n"
        + role["instruction"]
        + "\nSTATE:\n"
        + ctx
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    result = http_json(
        cfg["gateway_base_url"] + "/chat/completions",
        "POST",
        payload,
        key,
    )
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def local_gates() -> list[dict]:
    rows = []
    for cmd in ALLOWLIST:
        try:
            completed = subprocess.run(
                cmd,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=1200,
                check=False,
            )
            rows.append(
                {
                    "cmd": cmd,
                    "rc": completed.returncode,
                    "stdout": completed.stdout[-5000:],
                    "stderr": completed.stderr[-5000:],
                }
            )
        except (OSError, subprocess.SubprocessError) as exc:
            rows.append({"cmd": cmd, "rc": 127, "error": repr(exc)})
        if rows[-1]["rc"] != 0:
            break
    return rows


def cycle(cfg: dict) -> None:
    gates = local_gates()
    emit("local_gates", gates)
    try:
        models = discover(cfg)
    except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        emit("model_discovery_error", {"error": repr(exc)})
        models = []
    if not models:
        emit(
            "panel_degraded",
            {
                "reason": (
                    "no usable AI_GATEWAY_API_KEY/models; continuing local/GitHub gates"
                )
            },
        )
        return
    emit(
        "models",
        [
            {key: model.get(key) for key in ("id", "name", "released", "context_window", "tags")}
            for model in models
        ],
    )
    ctx = context()
    for index, role in enumerate(cfg["roles"]):
        model = models[index % len(models)]["id"]
        try:
            result = ask(model, role, ctx, cfg)
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
            result = {"error": repr(exc)}
        emit("review", {"role": role["name"], "model": model, "result": result})


def stop_handler(*_: object) -> None:
    global RUNNING
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    cfg = json.loads(CONFIG.read_text())
    STATE.mkdir(parents=True, exist_ok=True)
    interval = max(300, int(os.environ.get("FTOE_AUTOPILOT_INTERVAL", "1800")))
    emit(
        "daemon_start",
        {"pid": os.getpid(), "author": "Robert Frost", "interval_seconds": interval},
    )
    while RUNNING and not STOP.exists():
        try:
            cycle(cfg)
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
            emit("cycle_error", {"error": repr(exc)})
        for _ in range(interval):
            if not RUNNING or STOP.exists():
                break
            time.sleep(1)
    emit("daemon_stop", {"explicit_stop_file": STOP.exists()})


if __name__ == "__main__":
    main()
