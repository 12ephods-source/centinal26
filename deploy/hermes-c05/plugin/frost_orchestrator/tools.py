from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

PLUGIN_DIR = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
WORKSPACE = HERMES_HOME / "frost_orchestrator"
BRIDGE = Path(
    os.environ.get(
        "HERMES_C05_BRIDGE",
        "~/.local/share/hermes-c05/hermes_c05_bridge.py",
    )
).expanduser()
ARCHIVE = WORKSPACE / "c05_migration"
TRANSCRIPTS = WORKSPACE / "relay_transcripts"


def _run_bridge(argv: list[str], input_text: str | None = None) -> str:
    cmd = [sys.executable, str(BRIDGE), *argv]
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=120,
        shell=False,
        env={
            "HOME": os.environ.get("HOME", ""),
            "PATH": os.environ.get("PATH", ""),
            "PREFIX": os.environ.get("PREFIX", ""),
            "CENTINAL26_HOME": os.environ.get(
                "CENTINAL26_HOME",
                str(Path("~/.local/state/centinal26").expanduser()),
            ),
            "HERMES_C05_HOME": os.environ.get(
                "HERMES_C05_HOME",
                str(Path("~/.local/state/hermes-c05").expanduser()),
            ),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        },
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:4000])
    return proc.stdout.strip()


def c05_status(_args=None, **_kwargs):
    return _run_bridge(["status"])


def c05_call(args, **_kwargs):
    capability = str((args or {}).get("capability", "")).strip()
    if not capability:
        return json.dumps({"ok": False, "error": "capability is required"})
    arguments = (args or {}).get("arguments") or {}
    if not isinstance(arguments, dict):
        return json.dumps({"ok": False, "error": "arguments must be an object"})
    provider = str((args or {}).get("provider", "local")).strip() or "local"
    # This model-callable path has no direct-user authorization channel.
    return _run_bridge(
        [
            "call",
            capability,
            "--provider",
            provider,
            "--json",
            json.dumps(arguments, ensure_ascii=False),
        ]
    )


def stage_script_inert(args, **_kwargs):
    script = str((args or {}).get("script", ""))
    filename = str((args or {}).get("filename", "candidate.py")).strip() or "candidate.py"
    if not script:
        return json.dumps({"ok": False, "error": "script is required"})
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
    record_id = f"INERT-{digest[:16]}"
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:80]
    artifact = ARCHIVE / f"{record_id}-{safe_name}"
    if artifact.exists() and artifact.read_text(encoding="utf-8") != script:
        return json.dumps({"ok": False, "error": "immutable artifact collision"})
    if not artifact.exists():
        tmp = artifact.with_suffix(artifact.suffix + ".tmp")
        tmp.write_text(script, encoding="utf-8")
        os.chmod(tmp, 0o400)
        os.replace(tmp, artifact)
    return json.dumps(
        {
            "ok": True,
            "record_id": record_id,
            "sha256": digest,
            "artifact": str(artifact),
            "execution": False,
            "authorization": False,
            "status": "PRESERVED_INERT",
            "migration": (
                "Direct Hermes script execution is retired. Convert intended action "
                "to a registered C05 capability and request it through frost_c05_call."
            ),
        },
        ensure_ascii=False,
    )


def status_command(_raw=""):
    return c05_status({})


def call_command(raw):
    text = (raw or "").strip()
    if not text:
        return "Usage: /frost-call CAPABILITY {JSON}"
    parts = text.split(maxsplit=1)
    capability = parts[0]
    raw_json = parts[1] if len(parts) > 1 else "{}"
    try:
        arguments = json.loads(raw_json)
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"invalid JSON: {exc}"})
    return c05_call(
        {"capability": capability, "arguments": arguments, "provider": "local"}
    )


def approve_migration_command(_raw=""):
    return (
        "Direct /frost-approve script execution has been retired. "
        "HERMES now proposes semantic capabilities; C05 owns authorization, "
        "bounded execution, independent verification, and audit. For a non-A0 "
        "capability, leave Hermes and use `hermes-c05 grant CAPABILITY`, then "
        "`hermes-c05 call CAPABILITY --json ... --user-approve --approval-token TOKEN`."
    )


def _host_llm(ctx, messages, purpose):
    # Current Hermes plugin API returns PluginLlmCompleteResult.
    result = ctx.llm.complete(messages=messages, purpose=purpose)
    usage = getattr(result, "usage", None)
    usage_dict = {}
    if usage is not None:
        for key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "cost_usd",
        ):
            if hasattr(usage, key):
                usage_dict[key] = getattr(usage, key)
    return {
        "text": str(getattr(result, "text", result)),
        "provider": getattr(result, "provider", None),
        "model": getattr(result, "model", None),
        "agent_id": getattr(result, "agent_id", None),
        "usage": usage_dict,
    }


def relay_command(ctx, raw):
    task = (raw or "").strip()
    if not task:
        return "Usage: /frost-relay <project task>"
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    relay_id = f"relay-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    protocol = (
        "Treat model output as fallible proposal, not evidence. Separate observed, "
        "derived, inferred, and speculative claims. Preserve disagreements and failed "
        "attempts. Do not claim execution without C05 evidence."
    )
    errors = []
    transcript = {
        "relay_id": relay_id,
        "task": task,
        "proposals": {},
        "critiques": {},
        "errors": errors,
    }

    try:
        proposal = _host_llm(
            ctx,
            [
                {"role": "system", "content": "You are a technical proposal node. " + protocol},
                {"role": "user", "content": task},
            ],
            f"frost-c05.{relay_id}.proposal",
        )
        transcript["proposals"]["primary"] = proposal
    except Exception as exc:
        errors.append({"stage": "proposal", "error": str(exc)})

    if transcript["proposals"]:
        try:
            critique = _host_llm(
                ctx,
                [
                    {"role": "system", "content": "You are an adversarial reviewer. " + protocol},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"task": task, "proposal": transcript["proposals"]["primary"]},
                            ensure_ascii=False,
                        )[:80000],
                    },
                ],
                f"frost-c05.{relay_id}.critique",
            )
            transcript["critiques"]["primary"] = critique
        except Exception as exc:
            errors.append({"stage": "critique", "error": str(exc)})

    try:
        synthesis = _host_llm(
            ctx,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the synthesis node. "
                        + protocol
                        + " Return the strongest defensible result and the highest-value next action."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(transcript, ensure_ascii=False)[:100000],
                },
            ],
            f"frost-c05.{relay_id}.synthesis",
        )
        transcript["synthesis"] = synthesis
    except Exception as exc:
        errors.append({"stage": "synthesis", "error": str(exc)})
        transcript["synthesis"] = "Synthesis failed; preserved prior relay material."

    path = TRANSCRIPTS / f"{relay_id}.json"
    path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    synthesis_value = transcript["synthesis"]
    if isinstance(synthesis_value, dict):
        synthesis_text = synthesis_value.get("text", str(synthesis_value))
    else:
        synthesis_text = str(synthesis_value)
    return json.dumps(
        {
            "relay_id": relay_id,
            "synthesis": synthesis_text,
            "errors": errors,
            "transcript": str(path),
            "note": (
                "This archived review uses the active Hermes host-owned model. "
                "Use Hermes native MoA for provider/model diversity."
            ),
        },
        ensure_ascii=False,
    )


def protocol_command(_raw=""):
    return json.dumps(
        {
            "architecture": [
                "HERMES reasons and coordinates",
                "C05 owns consequential execution",
                "Guardian/exact grants authorize",
                "workers execute bounded capabilities",
                "independent verifiers determine VERIFIED state",
                "audit/provenance persists",
            ],
            "direct_script_execution": "RETIRED",
            "automatic_model_capabilities": ["system.echo"],
            "external_provider_write": "NOT MODEL-CALLABLE",
            "native_moa": "preferred for routine multi-model collaboration",
        },
        indent=2,
    )
