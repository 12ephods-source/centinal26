"""Split-authority FToE research supervisor.

The long-lived supervisor owns deterministic local gates and research-state
reconciliation, but has no HTTP client and does not parse provider secrets.
External model calls are delegated to a one-shot broker subprocess whose output
is treated as hostile/untrusted data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "physics/ftoe/autonomous_research_state.json"
PUB = ROOT / "physics/ftoe/publication_gate.json"
CLAIMS = ROOT / "physics/ftoe/claim_ledger.json"
ART = ROOT / "artifacts/ftoe-research-agent"
BROKER = ROOT / "scripts/ftoe_provider_broker.py"
SECRETS = pathlib.Path(os.environ.get("FTOE_PROVIDER_SECRETS", str(pathlib.Path.home() / ".config/ftoe-research/providers.secrets")))

ALLOWLIST = [
    [sys.executable, "scripts/ftoe_so10_group_theory_gate.py"],
    [sys.executable, "scripts/ftoe_so10_naturalness_gate.py", "--MU", "2.04990990688745e16", "--muI", "9.54e3", "--alphaU", "0.032067325570772874"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_group_theory_gate", "-v"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_422_gate", "-v"],
    [sys.executable, "-m", "unittest", "tests.test_ftoe_so10_uv_closure", "-v"],
]

GATE_PRIORITY = [
    "radiative_naturalness",
    "frozen_uv_action",
    "vacuum_and_mass_spectrum",
    "operator_basis_and_C_eff",
    "two_loop_rge_with_derived_thresholds",
    "proton_decay_from_frozen_spectrum",
    "dark_sector_joint_viability",
    "inflation_joint_likelihood",
    "microscopic_L4_derivation",
    "manuscript_claim_audit",
    "reproducibility_bundle",
]

SISTER_ATTACKS = [
    ("formal_derivation", "Attempt a direct derivation. Identify every assumption and any missing lemma or contraction."),
    ("counterexample", "Try to construct a concrete counterexample or lower-dimension operator that kills the claim."),
    ("numerical_stability", "Attack numerical conditioning, boundary conditions, hidden fitting, and parameter degeneracy."),
    ("independence_audit", "Look for circular validation, borrowed assumptions, source dependence, and non-independent evidence."),
    ("hostile_referee", "Assume the claim is wrong and identify the smallest decisive falsification test."),
]


def load_json(path: pathlib.Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def next_gate(pub: dict) -> tuple[str, str]:
    mandatory = pub.get("mandatory", {})
    for gate in GATE_PRIORITY:
        if mandatory.get(gate) != "PASS":
            return gate, mandatory.get(gate, "UNKNOWN")
    return "manuscript_claim_audit", mandatory.get("manuscript_claim_audit", "UNKNOWN")


def run_gate(command: list[str]) -> dict:
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=900, check=False)
    return {
        "cmd": command,
        "returncode": process.returncode,
        "stdout": process.stdout[-20000:],
        "stderr": process.stderr[-10000:],
    }


def sanitized_broker_env() -> dict[str, str]:
    keep = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}
    env = {key: value for key, value in os.environ.items() if key in keep}
    env["FTOE_PROVIDER_SECRETS"] = str(SECRETS)
    return env


def broker_json(arguments: list[str], prompt: str | None = None) -> dict:
    with tempfile.NamedTemporaryFile("w", prefix="ftoe-prompt-", suffix=".txt", delete=False) as handle:
        prompt_path = pathlib.Path(handle.name)
        if prompt is not None:
            handle.write(prompt)
    try:
        command = [sys.executable, str(BROKER), "--secrets", str(SECRETS), *arguments]
        if prompt is not None:
            command.extend(["--prompt-file", str(prompt_path)])
        process = subprocess.run(command, cwd=ROOT, env=sanitized_broker_env(), text=True, capture_output=True, timeout=240, check=False)
        if process.returncode != 0:
            return {"status": "ERROR", "error": process.stderr[-2000:] or f"broker rc={process.returncode}"}
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError:
            return {"status": "ERROR", "error": "broker returned non-JSON"}
    finally:
        try:
            prompt_path.unlink()
        except FileNotFoundError:
            pass


def configured_providers() -> list[str]:
    result = broker_json(["--list-configured"])
    providers = result.get("providers", [])
    return [provider for provider in providers if isinstance(provider, str)]


def validate_response(result: dict, allowed_refs: set[str]) -> dict:
    if result.get("status") != "OK":
        return result
    response = result.get("response")
    if not isinstance(response, dict):
        return {**result, "status": "ERROR", "error": "invalid response schema"}
    status = response.get("status")
    if status not in {"PASS", "REVIEW", "FAIL"}:
        response["status"] = "REVIEW"
    refs = response.get("evidence_refs", [])
    if not isinstance(refs, list):
        refs = []
    unknown = [ref for ref in refs if ref not in allowed_refs]
    response["evidence_refs"] = [ref for ref in refs if ref in allowed_refs]
    if unknown:
        response["status"] = "REVIEW"
        response["untrusted_evidence_refs"] = unknown[:50]
    if response["status"] == "PASS" and not response["evidence_refs"]:
        response["status"] = "REVIEW"
        response["downgrade_reason"] = "PASS_WITHOUT_VALID_EVIDENCE_REFS"
    result["response"] = response
    return result


def arbitration(panel: list[dict]) -> dict:
    accepted = [entry for entry in panel if entry.get("status") == "OK"]
    statuses = [entry.get("response", {}).get("status", "REVIEW") for entry in accepted]
    counts = {name: statuses.count(name) for name in ("PASS", "REVIEW", "FAIL")}
    disagreement = len(set(statuses)) > 1
    if counts["FAIL"]:
        conservative = "FAIL"
    elif counts["REVIEW"] or disagreement or counts["PASS"] < 2:
        conservative = "REVIEW"
    else:
        conservative = "PASS"
    return {"responses": len(accepted), "counts": counts, "disagreement": disagreement, "conservative_status": conservative}


def evidence_packet(pub: dict, gates: list[dict]) -> tuple[dict, set[str]]:
    refs: dict[str, str] = {}
    for path in (PUB, CLAIMS, ROOT / "physics/ftoe/uv_model_contract.json", ROOT / "physics/ftoe/g422_spectrum_registry.json"):
        if path.exists():
            refs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for index, gate in enumerate(gates):
        refs[f"gate:{index}"] = sha({"cmd": gate["cmd"], "rc": gate["returncode"], "stdout": gate["stdout"], "stderr": gate["stderr"]})
    packet = {"publication_gate": pub, "evidence_refs": refs, "deterministic_gate_summary": [{"cmd": g["cmd"], "returncode": g["returncode"]} for g in gates]}
    return packet, set(refs)


def publication_ready(gates: list[dict]) -> bool:
    pub = load_json(PUB, {})
    return bool(
        all(gate["returncode"] == 0 for gate in gates)
        and pub.get("status") == "PASS"
        and all(value == "PASS" for value in pub.get("mandatory", {}).values())
        and (ROOT / "docs/physics/FTOE_PUBLICATION_DRAFT.md").exists()
    )


def cycle() -> int:
    state = load_json(STATE, {"cycle": 0, "publication_ready": False})
    pub = load_json(PUB, {})
    gate, gate_status = next_gate(pub)
    gates = [run_gate(command) for command in ALLOWLIST]
    packet, allowed_refs = evidence_packet(pub, gates)
    evidence_digest = sha(packet)
    previous_digest = state.get("last_evidence_digest")
    same_gate = state.get("current_target_gate") == gate
    plateau = int(state.get("plateau_cycles", 0)) + 1 if same_gate and previous_digest == evidence_digest else 0
    strategy = "normal_review" if plateau < 2 else ("falsifier_design" if plateau < 4 else "deterministic_escalation")

    providers = configured_providers()
    max_calls = max(1, min(int(os.environ.get("FTOE_MAX_LLM_CALLS_PER_CYCLE", "5")), len(providers) or 1))
    if strategy == "deterministic_escalation":
        max_calls = min(max_calls, 2)
    panel: list[dict] = []
    for index, provider in enumerate(providers[:max_calls]):
        attack_name, attack = SISTER_ATTACKS[index % len(SISTER_ATTACKS)]
        prompt = (
            f"TARGET GATE: {gate} ({gate_status})\n"
            f"SISTER ATTACK MODE: {attack_name}\n{attack}\n"
            f"STRATEGY: {strategy}\n"
            "You cannot see other sister-agent verdicts. Do not seek consensus. "
            "Use only evidence identifiers present below.\n\n"
            + json.dumps(packet, sort_keys=True)
        )
        result = broker_json(["--provider", provider], prompt)
        result["attack_mode"] = attack_name
        panel.append(validate_response(result, allowed_refs))

    arb = arbitration(panel)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ART / timestamp
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "FTOE-RESEARCH-CYCLE-v4-split-authority",
        "timestamp": timestamp,
        "target_gate": gate,
        "target_status": gate_status,
        "strategy": strategy,
        "plateau_cycles": plateau,
        "evidence_digest": evidence_digest,
        "gates": gates,
        "panel": panel,
        "arbitration": arb,
        "publication_ready": publication_ready(gates),
        "security_boundary": {
            "supervisor_has_http_client": False,
            "supervisor_parses_provider_secrets": False,
            "broker_has_subprocess_execution": False,
            "same_uid_hard_isolation": False,
        },
    }
    raw = json.dumps(record, indent=2, sort_keys=True) + "\n"
    (out / "cycle.json").write_text(raw)
    (out / "SHA256.txt").write_text(hashlib.sha256(raw.encode()).hexdigest() + "  cycle.json\n")
    state.update(
        {
            "cycle": int(state.get("cycle", 0)) + 1,
            "last_cycle": timestamp,
            "publication_ready": record["publication_ready"],
            "current_target_gate": gate,
            "last_evidence_digest": evidence_digest,
            "plateau_cycles": plateau,
            "last_arbitration": arb,
            "last_artifact": str(out.relative_to(ROOT)),
            "strategy": strategy,
        }
    )
    save_json(STATE, state)
    return 0 if all(gate_result["returncode"] == 0 for gate_result in gates) else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("FTOE_AGENT_INTERVAL", "3600")))
    args = parser.parse_args()
    while True:
        code = cycle()
        if args.once:
            return code
        time.sleep(max(300, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
