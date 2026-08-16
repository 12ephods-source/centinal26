from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .advance import advance_until_idle, build_advance_engine
from .event_state import EventStore, rebuild_state
from .frost_call_adapter import ingest_frost_call
from .qualification import platform_identity

Json = dict[str, Any]
CAMPAIGN_SCHEMA_VERSION = 1
CHECKPOINT_NAME = "device-campaign-checkpoint.json"
REPORT_NAME = "device-validation-report.json"
MANIFEST_NAME = "device-validation-manifest.json"
PHASE_AWAITING_REBOOT = "AWAITING_REBOOT"
PHASE_COMPLETE = "COMPLETE"
DECISION_PERSISTENT_VALIDATED = "PERSISTENT_VALIDATED"
DECISION_WAITING_FOR_REBOOT = "WAITING_FOR_REBOOT"


class DeviceCampaignError(RuntimeError):
    """A device qualification campaign violated a hard validation invariant."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> Json:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DeviceCampaignError(f"expected JSON object: {path}")
    return value


def _read_boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise DeviceCampaignError(f"cannot read Android/Linux boot identity: {error}") from error
    if not value:
        raise DeviceCampaignError("kernel boot identity is empty")
    return value


def _require_physical_termux() -> Json:
    identity = platform_identity()
    if not (
        identity.get("termux") is True
        and identity.get("android") is True
        and identity.get("physical_device_inferred") is True
    ):
        raise DeviceCampaignError(
            "device qualification requires a physical Android Termux runtime"
        )
    return identity


def _verify_boot_hook(boot_hook: Path) -> str:
    resolved = boot_hook.expanduser().resolve()
    if not resolved.is_file():
        raise DeviceCampaignError(f"Termux:Boot hook is missing: {resolved}")
    return _sha256_file(resolved)


def _state_home(campaign: Path) -> Path:
    return campaign / "state"


def _event_store(campaign: Path) -> EventStore:
    return EventStore(_state_home(campaign) / "events.sqlite3")


def _probe_envelope(campaign_id: str, phase: str) -> Json:
    request_id = f"device-campaign:{campaign_id}:{phase.lower()}"
    return {
        "protocol_version": "frost-call/1.0",
        "request_id": request_id,
        "operation": "intent.submit",
        "parameters": {
            "capability": "system.echo",
            "payload": {
                "campaign_id": campaign_id,
                "phase": phase,
                "probe": "physical-canonical-execution",
            },
        },
        "caller": {"id": "device-qualification", "type": "system"},
        "provenance": {
            "campaign_id": campaign_id,
            "phase": phase,
            "purpose": "physical-persistence-qualification",
        },
        "idempotency_key": request_id,
    }


def _run_canonical_probe(campaign: Path, campaign_id: str, phase: str) -> Json:
    store = _event_store(campaign)
    runtime = build_advance_engine(_state_home(campaign))
    try:
        ingested = ingest_frost_call(store, _probe_envelope(campaign_id, phase))
        task_id = ingested.canonical.task_id

        blocked = advance_until_idle(store, runtime, authorize=False, max_tasks=1)
        if blocked.executed or blocked.stop_reason != "APPROVAL_REQUIRED":
            raise DeviceCampaignError(
                "canonical execution did not fail closed before explicit authorization"
            )
        if blocked.blocked.get(task_id) != "APPROVAL_REQUIRED":
            raise DeviceCampaignError("task was not explicitly blocked on authorization")

        executed = advance_until_idle(store, runtime, authorize=True, max_tasks=1)
        if executed.completed != [task_id] or executed.failed:
            raise DeviceCampaignError("authorized physical probe did not complete successfully")

        state = rebuild_state(store.events())
        task = state.tasks.get(task_id)
        if not isinstance(task, dict) or task.get("status") != "COMPLETE":
            raise DeviceCampaignError("canonical task did not reconcile to COMPLETE")
        if not store.verify_chain():
            raise DeviceCampaignError("canonical event chain is invalid after execution")

        row = runtime.store.db.execute(
            "SELECT state,evidence_path FROM jobs WHERE capability=? ORDER BY rowid DESC LIMIT 1",
            ("system.echo",),
        ).fetchone()
        if row is None or row["state"] != "verified" or not row["evidence_path"]:
            raise DeviceCampaignError("runtime did not persist verified execution evidence")
        evidence_path = Path(row["evidence_path"])
        if not runtime.evidence.verify(evidence_path):
            raise DeviceCampaignError("runtime evidence failed independent re-verification")
        if not runtime.audit.verify():
            raise DeviceCampaignError("runtime audit chain is invalid")

        return {
            "phase": phase,
            "request_id": ingested.request_id,
            "envelope_sha256": ingested.envelope_sha256,
            "task_id": task_id,
            "task_status": task["status"],
            "authorization_gate": "PASS",
            "runtime_state": row["state"],
            "evidence_path": str(evidence_path),
            "evidence_sha256": _sha256_file(evidence_path),
            "event_chain_valid": True,
            "runtime_audit_valid": True,
        }
    finally:
        store.close()
        runtime.store.db.close()


def _verify_probe(campaign: Path, probe: Json) -> bool:
    task_id = probe.get("task_id")
    evidence_path = probe.get("evidence_path")
    evidence_sha256 = probe.get("evidence_sha256")
    if not isinstance(task_id, str) or not task_id:
        return False
    if not isinstance(evidence_path, str) or not evidence_path:
        return False
    if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
        return False

    store = _event_store(campaign)
    runtime = build_advance_engine(_state_home(campaign))
    try:
        if not store.verify_chain():
            return False
        state = rebuild_state(store.events())
        task = state.tasks.get(task_id)
        if not isinstance(task, dict) or task.get("status") != "COMPLETE":
            return False
        path = Path(evidence_path)
        if not path.is_file() or _sha256_file(path) != evidence_sha256:
            return False
        return runtime.evidence.verify(path) and runtime.audit.verify()
    finally:
        store.close()
        runtime.store.db.close()


def prepare_device_campaign(campaign: Path, *, boot_hook: Path) -> Json:
    campaign = campaign.expanduser().resolve()
    if campaign.exists():
        raise DeviceCampaignError(f"campaign path already exists: {campaign}")

    identity = _require_physical_termux()
    boot_hook = boot_hook.expanduser().resolve()
    boot_hook_sha256 = _verify_boot_hook(boot_hook)
    boot_id = _read_boot_id()
    campaign_id = str(uuid.uuid4())
    campaign.mkdir(parents=True)

    pre_probe = _run_canonical_probe(campaign, campaign_id, "PRE_REBOOT")
    checkpoint: Json = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "phase": PHASE_AWAITING_REBOOT,
        "created_at": _utc_now_iso(),
        "source_commit": os.environ.get("CENTINAL26_CAMPAIGN_SOURCE_SHA"),
        "platform": identity,
        "pre_boot_id": boot_id,
        "boot_hook": str(boot_hook),
        "boot_hook_sha256": boot_hook_sha256,
        "pre_reboot_probe": pre_probe,
        "device_validated": True,
    }
    _atomic_write_json(campaign / CHECKPOINT_NAME, checkpoint)
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "phase": PHASE_AWAITING_REBOOT,
        "decision": DECISION_WAITING_FOR_REBOOT,
        "campaign": str(campaign),
        "pre_boot_id": boot_id,
        "task_id": pre_probe["task_id"],
        "device_validated": True,
        "persistent_validated": False,
        "next_action": "REBOOT_ANDROID",
    }


def _manifest_entries(campaign: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in sorted(campaign.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        relative = path.relative_to(campaign).as_posix()
        entries[relative] = _sha256_file(path)
    return entries


def resume_device_campaign(campaign: Path, *, boot_hook: Path | None = None) -> Json:
    campaign = campaign.expanduser().resolve()
    identity = _require_physical_termux()
    checkpoint = _read_json(campaign / CHECKPOINT_NAME)
    if checkpoint.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
        raise DeviceCampaignError("unsupported device campaign checkpoint schema")
    if checkpoint.get("phase") != PHASE_AWAITING_REBOOT:
        if (campaign / REPORT_NAME).is_file() and verify_device_campaign(campaign):
            return _read_json(campaign / REPORT_NAME)
        raise DeviceCampaignError("device campaign is not awaiting reboot")

    campaign_id = checkpoint.get("campaign_id")
    pre_boot_id = checkpoint.get("pre_boot_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise DeviceCampaignError("checkpoint campaign_id is invalid")
    if not isinstance(pre_boot_id, str) or not pre_boot_id:
        raise DeviceCampaignError("checkpoint pre_boot_id is invalid")

    current_boot_id = _read_boot_id()
    if current_boot_id == pre_boot_id:
        return {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": campaign_id,
            "phase": PHASE_AWAITING_REBOOT,
            "decision": DECISION_WAITING_FOR_REBOOT,
            "campaign": str(campaign),
            "pre_boot_id": pre_boot_id,
            "current_boot_id": current_boot_id,
            "device_validated": True,
            "persistent_validated": False,
            "next_action": "REBOOT_ANDROID",
        }

    configured_hook = Path(str(checkpoint.get("boot_hook", ""))).expanduser().resolve()
    if boot_hook is not None and boot_hook.expanduser().resolve() != configured_hook:
        raise DeviceCampaignError("resume boot-hook path does not match the checkpoint")
    if _verify_boot_hook(configured_hook) != checkpoint.get("boot_hook_sha256"):
        raise DeviceCampaignError("Termux:Boot hook changed between campaign phases")

    pre_probe = checkpoint.get("pre_reboot_probe")
    if not isinstance(pre_probe, dict) or not _verify_probe(campaign, pre_probe):
        raise DeviceCampaignError("pre-reboot execution evidence no longer verifies")

    post_probe = _run_canonical_probe(campaign, campaign_id, "POST_REBOOT")
    report: Json = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "phase": PHASE_COMPLETE,
        "decision": DECISION_PERSISTENT_VALIDATED,
        "completed_at": _utc_now_iso(),
        "source_commit": checkpoint.get("source_commit"),
        "platform": identity,
        "pre_boot_id": pre_boot_id,
        "post_boot_id": current_boot_id,
        "boot_id_changed": True,
        "boot_hook": str(configured_hook),
        "boot_hook_sha256": checkpoint.get("boot_hook_sha256"),
        "pre_reboot_probe": pre_probe,
        "post_reboot_probe": post_probe,
        "checks": {
            "physical_android_termux": True,
            "boot_identity_changed": True,
            "boot_hook_unchanged": True,
            "pre_reboot_probe_verified": True,
            "post_reboot_probe_verified": True,
            "canonical_event_chain_valid": True,
            "runtime_audit_chain_valid": True,
        },
        "promotion_scope": "PERSISTENT_VALIDATED",
        "device_validated": True,
        "persistent_validated": True,
        "autonomous_validated": False,
    }
    _atomic_write_json(campaign / REPORT_NAME, report)
    manifest = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "algorithm": "sha256",
        "files": _manifest_entries(campaign),
    }
    _atomic_write_json(campaign / MANIFEST_NAME, manifest)

    if not verify_device_campaign(campaign):
        raise DeviceCampaignError("final device evidence failed self-verification")
    return report


def _safe_manifest_files(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict) or not value:
        return None
    safe: dict[str, str] = {}
    for relative, digest in value.items():
        if not isinstance(relative, str) or not relative:
            return None
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            return None
        if not isinstance(digest, str) or len(digest) != 64:
            return None
        try:
            int(digest, 16)
        except ValueError:
            return None
        safe[relative] = digest
    return safe


def verify_device_campaign(campaign: Path) -> bool:
    campaign = campaign.expanduser().resolve()
    try:
        manifest = _read_json(campaign / MANIFEST_NAME)
        if manifest.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
            return False
        files = _safe_manifest_files(manifest.get("files"))
        if files is None:
            return False
        if set(files) != set(_manifest_entries(campaign)):
            return False
        for relative, digest in files.items():
            path = (campaign / relative).resolve()
            try:
                path.relative_to(campaign)
            except ValueError:
                return False
            if not path.is_file() or _sha256_file(path) != digest:
                return False

        checkpoint = _read_json(campaign / CHECKPOINT_NAME)
        report = _read_json(campaign / REPORT_NAME)
        if checkpoint.get("campaign_id") != manifest.get("campaign_id"):
            return False
        if report.get("campaign_id") != manifest.get("campaign_id"):
            return False
        if report.get("decision") != DECISION_PERSISTENT_VALIDATED:
            return False
        if report.get("phase") != PHASE_COMPLETE:
            return False
        if report.get("promotion_scope") != "PERSISTENT_VALIDATED":
            return False
        if report.get("device_validated") is not True:
            return False
        if report.get("persistent_validated") is not True:
            return False
        if report.get("autonomous_validated") is not False:
            return False
        if report.get("pre_boot_id") == report.get("post_boot_id"):
            return False
        checks = report.get("checks")
        if not isinstance(checks, dict) or not checks or not all(checks.values()):
            return False

        pre_probe = report.get("pre_reboot_probe")
        post_probe = report.get("post_reboot_probe")
        if not isinstance(pre_probe, dict) or not isinstance(post_probe, dict):
            return False
        if not _verify_probe(campaign, pre_probe) or not _verify_probe(campaign, post_probe):
            return False

        store = _event_store(campaign)
        runtime = build_advance_engine(_state_home(campaign))
        try:
            if not store.verify_chain() or not runtime.audit.verify():
                return False
            rows = runtime.store.db.execute(
                "SELECT state,evidence_path FROM jobs WHERE capability=? ORDER BY rowid",
                ("system.echo",),
            ).fetchall()
            if len(rows) != 2 or any(row["state"] != "verified" for row in rows):
                return False
            if any(
                not row["evidence_path"]
                or not runtime.evidence.verify(Path(row["evidence_path"]))
                for row in rows
            ):
                return False
        finally:
            store.close()
            runtime.store.db.close()
        return True
    except (
        DeviceCampaignError,
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
