from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "frost.scientific_autocycle.v1"
META_PREFIX = "# FROST-CYCLE:"
MARKER = "# FROST-AUTORUN:2"
DEFAULT_ROOT = Path.home() / ".local/share/frost-scientific-autocycle"
DEFAULT_PERSPECTIVES = (
    "engineering", "empirical", "causal", "falsification",
    "information_value", "discovery", "resource", "epistemic",
)
DANGEROUS = (
    (r"\brm\s+-[^\n]*r[^\n]*f\b", "recursive_force_delete"),
    (r"\bmkfs(?:\.|\s)", "filesystem_format"),
    (r"\bdd\b[^\n]*\bof=/dev/", "raw_device_write"),
    (r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:bash|sh)\b", "remote_pipe_to_shell"),
    (r"\beval\s+", "dynamic_shell_eval"),
    (r"\bchmod\s+(?:-R\s+)?777\b", "world_writable_permissions"),
    (r"\b(?:sudo|su)\b", "privilege_escalation_request"),
)
VIBEWARE = (
    (r"\bTODO\b|\bFIXME\b", "unfinished_placeholder"),
    (r"NotImplementedError", "not_implemented_path"),
    (r"\b(?:pretend|fake|simulated)_pass\b", "synthetic_pass_marker"),
    (r"\bassert\s+True\b", "non_test_assertion"),
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def validate_meta(value: dict[str, Any]) -> dict[str, Any]:
    goal, success = value.get("goal"), value.get("success")
    if not isinstance(goal, str) or not goal.strip() or not isinstance(success, dict):
        raise ValueError("goal must be non-empty and success must be an object")
    exit_code = success.get("exit_code", 0)
    if not isinstance(exit_code, int):
        raise ValueError("success.exit_code must be an integer")
    for key in ("required_text", "forbidden_text"):
        items = success.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
            raise ValueError(f"success.{key} must be a list of strings")
    limits = value.get("limits", {})
    max_iterations = limits.get("max_iterations", 8)
    timeout = limits.get("episode_timeout_seconds", 120)
    if not isinstance(max_iterations, int) or not 1 <= max_iterations <= 100:
        raise ValueError("max_iterations must be 1..100")
    if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
        raise ValueError("episode_timeout_seconds must be 1..3600")
    perspectives = value.get("perspectives", list(DEFAULT_PERSPECTIVES))
    if not isinstance(perspectives, list) or not perspectives or any(x not in DEFAULT_PERSPECTIVES for x in perspectives):
        raise ValueError("unsupported perspectives")
    providers = value.get("agent_providers", ["deterministic"])
    if not isinstance(providers, list) or any(not isinstance(x, str) for x in providers):
        raise ValueError("agent_providers must be strings")
    return {
        "goal": goal.strip(),
        "success": {"exit_code": exit_code, "required_text": success.get("required_text", []), "forbidden_text": success.get("forbidden_text", [])},
        "limits": {"max_iterations": max_iterations, "episode_timeout_seconds": timeout},
        "perspectives": perspectives,
        "agent_providers": providers,
        "origin": value.get("origin", {}),
        "capabilities": value.get("capabilities", {}),
        "notes": value.get("notes", ""),
    }


def load_cycle_meta(raw: str) -> dict[str, Any]:
    for line in raw.splitlines():
        if line.strip().startswith(META_PREFIX):
            try:
                value = json.loads(line.strip()[len(META_PREFIX):].strip())
            except json.JSONDecodeError as exc:
                raise ValueError("FROST-CYCLE metadata is invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError("FROST-CYCLE metadata must be an object")
            return validate_meta(value)
    raise ValueError("FROST-AUTORUN:2 requires # FROST-CYCLE metadata")


def parse_autorun_v2(raw: str) -> tuple[str, str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip("\n")
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        raise ValueError("clipboard is empty")
    marker = lines[first].strip()
    if marker != MARKER and not marker.startswith(MARKER + " "):
        raise ValueError("clipboard text is not marked for Frost scientific autocycle")
    language = "python" if ("shell=python" in marker or "lang=python" in marker) else "bash"
    body = "\n".join(line for i, line in enumerate(lines) if i != first and not line.strip().startswith(META_PREFIX)).strip("\n") + "\n"
    if not body.strip() or "\x00" in body:
        raise ValueError("invalid or empty candidate body")
    return language, body


def stage_clipboard(raw: str, root: Path) -> dict[str, Any]:
    meta = load_cycle_meta(raw)
    language, body = parse_autorun_v2(raw)
    intake = root / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    digest = sha256_text(body)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    suffix = ".py" if language == "python" else ".sh"
    raw_path = intake / f"{stamp}-{digest[:16]}.clipboard.txt"
    candidate = intake / f"{stamp}-{digest[:16]}{suffix}"
    raw_path.write_text(raw, encoding="utf-8")
    candidate.write_text(body, encoding="utf-8")
    os.chmod(raw_path, 0o600); os.chmod(candidate, 0o700)
    pending = {
        "schema": "frost.scientific_autocycle.pending.v1", "status": "STAGED", "staged_at": now_iso(),
        "candidate_sha256": digest, "raw_clipboard_sha256": sha256_file(raw_path),
        "candidate_path": str(candidate), "clipboard_path": str(raw_path), "language": language,
        "meta_sha256": sha256_text(canonical_json(meta)),
    }
    write_json(root / "pending.json", pending)
    return pending


@dataclass(frozen=True)
class GuardianFinding:
    category: str
    severity: str
    detail: str


@dataclass(frozen=True)
class GuardianReport:
    verdict: str
    findings: tuple[GuardianFinding, ...]
    script_sha256: str
    language: str

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "findings": [asdict(x) for x in self.findings], "script_sha256": self.script_sha256, "language": self.language}


def inspect_candidate(path: Path, language: str) -> GuardianReport:
    text, findings = path.read_text(encoding="utf-8"), []
    if language == "python":
        try: ast.parse(text)
        except SyntaxError as exc: findings.append(GuardianFinding("syntax", "REJECT", f"python syntax: {exc.msg}"))
    elif language == "bash":
        bash = shutil.which("bash")
        if bash:
            check = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True, check=False)
            if check.returncode: findings.append(GuardianFinding("syntax", "REJECT", check.stderr.strip() or "bash syntax failed"))
    else:
        findings.append(GuardianFinding("language", "REJECT", "unsupported language"))
    for pattern, name in DANGEROUS:
        if re.search(pattern, text, re.I): findings.append(GuardianFinding("dangerous_effect", "REJECT", name))
    for pattern, name in VIBEWARE:
        if re.search(pattern, text, re.I): findings.append(GuardianFinding("vibeware", "REVIEW", name))
    verdict = "REJECT" if any(x.severity == "REJECT" for x in findings) else "REVIEW" if findings else "PASS"
    return GuardianReport(verdict, tuple(findings), sha256_file(path), language)


def goal_satisfied(meta: dict[str, Any], exit_code: int, output: str) -> tuple[bool, list[dict[str, Any]]]:
    success, checks = meta["success"], []
    checks.append({"check": "exit_code", "expected": success["exit_code"], "actual": exit_code, "pass": exit_code == success["exit_code"]})
    checks += [{"check": "required_text", "value": x, "pass": x in output} for x in success["required_text"]]
    checks += [{"check": "forbidden_text", "value": x, "pass": x not in output} for x in success["forbidden_text"]]
    return all(x["pass"] for x in checks), checks


def perspective_findings(meta: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, str]]:
    facts = {
        "engineering": "acceptance checks passed" if episode["goal_satisfied"] else "acceptance checks did not pass",
        "empirical": f"exit={episode['exit_code']} duration={episode['duration_seconds']}s output_bytes={len(episode['output'].encode())}",
        "causal": "execution alone does not establish a causal explanation; prefer discriminating interventions",
        "falsification": "seek a counterexample capable of overturning the leading interpretation",
        "information_value": "prefer the next test that separates competing explanations per unit cost",
        "discovery": "preserve unexpected residuals as anomaly candidates",
        "resource": f"compare improvement value with remaining iteration budget after {episode['duration_seconds']}s",
        "epistemic": "separate observation, measurement, interpretation and conclusion; self-reported PASS is not the oracle",
    }
    return [{"perspective": name, "finding": facts[name]} for name in meta["perspectives"]]


def adjudicate_perspectives(meta: dict[str, Any], episode: dict[str, Any]) -> dict[str, Any]:
    if episode["goal_satisfied"]:
        desired, situation = ("engineering", "empirical", "falsification", "epistemic"), "nominal_success"
    elif episode["exit_code"] != 0:
        desired, situation = ("engineering", "empirical", "resource", "falsification"), "execution_failure"
    else:
        desired, situation = ("empirical", "information_value", "falsification", "discovery", "epistemic"), "acceptance_mismatch"
    return {"situation": situation, "selected_perspectives": [x for x in desired if x in meta["perspectives"]], "principle": "best perspective by situation; no permanent global winner"}


def derive_questions_and_hypotheses(episode: dict[str, Any]) -> dict[str, list[str]]:
    if episode["exit_code"] != 0:
        return {"questions": ["Which observed condition caused the non-zero exit code?"], "hypotheses": ["implementation defect", "missing dependency or capability", "inconsistent experiment contract"]}
    if not episode["goal_satisfied"]:
        return {"questions": ["Why did successful execution fail the acceptance predicate?"], "hypotheses": ["wrong result", "mismatched oracle", "unmodeled condition"]}
    return {"questions": ["What falsification test could overturn this nominal success?"], "hypotheses": ["goal holds in the observed environment but may fail at an untested boundary"]}


def local_agent_registry() -> dict[str, dict[str, Any]]:
    path = Path(os.environ.get("FROST_AUTOCYCLE_AGENT_REGISTRY", str(Path.home()/".config/frost/autocycle_agents.json"))).expanduser()
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}
    return data if isinstance(data, dict) else {}


def run_external_agent(provider: str, prompt: str, candidate: Path, timeout: int) -> dict[str, Any]:
    if provider == "deterministic": return {"provider": provider, "status": "AVAILABLE", "finding": "built-in scientific perspectives generated", "revision": None}
    spec = local_agent_registry().get(provider)
    if not isinstance(spec, dict): return {"provider": provider, "status": "UNAVAILABLE", "reason": "provider not registered locally", "revision": None}
    argv, mode = spec.get("argv"), spec.get("mode", "critique")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv): return {"provider": provider, "status": "UNAVAILABLE", "reason": "invalid argv", "revision": None}
    exe = shutil.which(argv[0])
    if not exe: return {"provider": provider, "status": "UNAVAILABLE", "reason": "executable missing", "revision": None}
    rendered = [exe if i == 0 else x.replace("{candidate}", str(candidate)).replace("{prompt}", prompt) for i, x in enumerate(argv)]
    try: completed = subprocess.run(rendered, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired: return {"provider": provider, "status": "TIMEOUT", "revision": None}
    result = {"provider": provider, "status": "COMPLETED", "exit_code": completed.returncode, "stdout": completed.stdout[-20000:], "stderr": completed.stderr[-10000:], "mode": mode, "revision": None}
    if mode == "edit" and completed.returncode == 0 and candidate.is_file(): result["revision"] = candidate.read_text(encoding="utf-8")
    return result


class CycleStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True); self.conn = sqlite3.connect(path); self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, kind TEXT, payload TEXT, prev_hash TEXT, event_hash TEXT)"); self.conn.commit()
    def append(self, kind: str, payload: dict[str, Any]) -> str:
        row = self.conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone(); prev = row[0] if row else "0"*64
        at = now_iso(); event_hash = sha256_text(canonical_json({"at": at, "kind": kind, "payload": payload, "prev_hash": prev}))
        self.conn.execute("INSERT INTO events(at,kind,payload,prev_hash,event_hash) VALUES(?,?,?,?,?)", (at,kind,canonical_json(payload),prev,event_hash)); self.conn.commit(); return event_hash
    def close(self) -> None: self.conn.close()


def execute_candidate(path: Path, language: str, timeout: int, cwd: Path) -> dict[str, Any]:
    command = [sys.executable, str(path)] if language == "python" else [shutil.which("bash") or "bash", str(path)]
    started = time.time()
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False); timed_out = False
        code, stdout, stderr = completed.returncode, completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out, code = True, 124; stdout = exc.stdout if isinstance(exc.stdout, str) else ""; stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    return {"exit_code": code, "stdout": stdout, "stderr": stderr, "output": stdout+stderr, "duration_seconds": round(time.time()-started,6), "timed_out": timed_out}


def scientific_prompt(meta: dict[str, Any], episode: dict[str, Any]) -> str:
    compact = {k:v for k,v in episode.items() if k not in {"output","perspectives"}}
    return f"Goal: {meta['goal']}\nObserved: {canonical_json(compact)}\nCriticize, compare explanations, propose the most discriminating next experiment, and improve only the working candidate if configured to edit. Never claim success unless the acceptance predicate passes."


def run_cycle(candidate: Path, meta: dict[str, Any], root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True); os.chmod(root, 0o700)
    cycle_id = sha256_text(canonical_json({"candidate":sha256_file(candidate),"meta":meta}))[:24]
    cycle = root/cycle_id; revisions, episodes = cycle/"revisions", cycle/"episodes"; revisions.mkdir(parents=True, exist_ok=True); episodes.mkdir(parents=True, exist_ok=True)
    store, text, language, parent = CycleStore(cycle/"cycle.sqlite3"), candidate.read_text(encoding="utf-8"), ("python" if candidate.suffix==".py" else "bash"), None
    status, last = "NO_IMPROVING_REVISION", None
    try:
        for iteration in range(1, meta["limits"]["max_iterations"]+1):
            revision_sha = sha256_text(text); revision = revisions/f"{iteration:04d}-{revision_sha[:16]}{candidate.suffix}"; revision.write_text(text, encoding="utf-8"); os.chmod(revision,0o700)
            store.append("revision", {"iteration":iteration,"sha256":revision_sha,"parent_sha256":parent,"path":str(revision)})
            guardian = inspect_candidate(revision, language); store.append("guardian", {"iteration":iteration,**guardian.to_dict()})
            if guardian.verdict == "REJECT": status, last = "POLICY_BLOCKED", {"iteration":iteration,"guardian":guardian.to_dict()}; break
            if guardian.verdict == "REVIEW": episode = {"iteration":iteration,"exit_code":126,"stdout":"","stderr":"guardian review required","output":"guardian review required","duration_seconds":0.0,"timed_out":False,"goal_satisfied":False,"checks":[]}
            else:
                episode = execute_candidate(revision, language, meta["limits"]["episode_timeout_seconds"], cycle); episode["goal_satisfied"], episode["checks"] = goal_satisfied(meta, episode["exit_code"], episode["output"])
            episode["guardian"] = guardian.to_dict(); episode["perspectives"] = perspective_findings(meta, episode); episode["perspective_adjudication"] = adjudicate_perspectives(meta, episode); episode["analysis"] = derive_questions_and_hypotheses(episode)
            record = {k:v for k,v in episode.items() if k!="output"}; record["output_sha256"] = sha256_text(episode["output"]); write_json(episodes/f"{iteration:04d}.json", record); store.append("episode", record); last = record
            if episode["goal_satisfied"] and guardian.verdict == "PASS": status = "GOAL_VERIFIED"; break
            if episode["timed_out"]: status = "RESOURCE_LIMIT_REACHED"
            prompt, proposed, results = scientific_prompt(meta, episode), None, []
            for provider in meta["agent_providers"]:
                working = cycle/f"agent-work-{iteration}{candidate.suffix}"; working.write_text(text, encoding="utf-8")
                result = run_external_agent(provider, prompt, working, meta["limits"]["episode_timeout_seconds"]); results.append({k:v for k,v in result.items() if k!="revision"})
                if isinstance(result.get("revision"), str) and result["revision"] != text: proposed = result["revision"]; break
            store.append("agent_panel", {"iteration":iteration,"results":results}); write_json(episodes/f"{iteration:04d}-agents.json", results)
            if proposed is None: break
            parent, text = revision_sha, proposed
        else: status = "RESOURCE_LIMIT_REACHED"
        report = {"schema":SCHEMA,"cycle_id":cycle_id,"status":status,"goal":meta["goal"],"origin":meta.get("origin",{}),"initial_candidate_sha256":sha256_file(candidate),"final_candidate_sha256":sha256_text(text),"last_episode":last,"created_at":now_iso(),"cycle_root":str(cycle),"database":str(cycle/"cycle.sqlite3"),"report_return":"stdout_and_cycle_root","promotion_performed":False}
        report["report_sha256"] = sha256_text(canonical_json(report)); write_json(cycle/"report.json", report); store.append("final_report", report); return report
    finally: store.close()


def run_pending_clipboard(root: Path) -> dict[str, Any]:
    pending = root/"pending.json"
    if not pending.is_file(): return {"schema":SCHEMA,"status":"NO_PENDING_CYCLE","promotion_performed":False}
    running = root/f"running-{os.getpid()}.json"; pending.replace(running)
    try:
        data = json.loads(running.read_text(encoding="utf-8")); candidate = Path(data["candidate_path"]).resolve(strict=True); clipboard = Path(data["clipboard_path"]).resolve(strict=True)
        if sha256_file(candidate)!=data["candidate_sha256"] or sha256_file(clipboard)!=data["raw_clipboard_sha256"]: raise RuntimeError("staged evidence hash mismatch")
        return run_cycle(candidate, load_cycle_meta(clipboard.read_text(encoding="utf-8")), root)
    finally: running.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Frost Scientific Autocycle"); mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stage-stdin", action="store_true"); mode.add_argument("--run-pending", action="store_true"); mode.add_argument("--candidate")
    parser.add_argument("--clipboard-file"); parser.add_argument("--root", default=str(DEFAULT_ROOT)); args = parser.parse_args(); root = Path(args.root).expanduser()
    if args.stage_stdin:
        pending = stage_clipboard(sys.stdin.read(), root); print(json.dumps(pending,indent=2,sort_keys=True)); print("FROST_AUTOCYCLE_STAGED"); return 0
    if args.run_pending: report = run_pending_clipboard(root)
    else:
        if not args.clipboard_file: parser.error("--clipboard-file is required with --candidate")
        candidate, clipboard = Path(args.candidate).expanduser().resolve(strict=True), Path(args.clipboard_file).expanduser().resolve(strict=True)
        report = run_cycle(candidate, load_cycle_meta(clipboard.read_text(encoding="utf-8")), root)
    print(json.dumps(report,indent=2,sort_keys=True)); print("FROST_AUTOCYCLE_REPORT_READY"); return 0 if report["status"]=="GOAL_VERIFIED" else 3


if __name__ == "__main__": raise SystemExit(main())
