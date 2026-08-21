"""Install and verify the canonical Frost protocol in writable project targets."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocols" / "FROST_MASTER_PROJECT_PROTOCOL_v2.md"
METADATA = ROOT / "protocols" / "frost_master_protocol_v2.json"
STATES = {"INSTALLED_VERIFIED", "OUTDATED", "CONFLICT", "PROPAGATION_BLOCKED_PLATFORM", "NOT_ATTEMPTED"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(target: Path) -> dict[str, str]:
    target.mkdir(parents=True, exist_ok=True)
    destination = target / "PROMPT_BOOTSTRAP.md"
    state = "NOT_ATTEMPTED"
    if destination.exists() and destination.read_bytes() != PROTOCOL.read_bytes():
        backup = target / f"PROMPT_BOOTSTRAP.pre-v2.{digest(destination)[:12]}.md"
        if not backup.exists():
            shutil.copy2(destination, backup)
        state = "OUTDATED"
    shutil.copy2(PROTOCOL, destination)
    if digest(destination) == digest(PROTOCOL):
        state = "INSTALLED_VERIFIED"
    record = {
        "protocol_id": json.loads(METADATA.read_text())["protocol_id"],
        "version": json.loads(METADATA.read_text())["version"],
        "sha256": digest(PROTOCOL),
        "target": str(target.resolve()),
        "installation_status": state,
        "verification_status": "VERIFIED" if state == "INSTALLED_VERIFIED" else "UNVERIFIED",
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    assert state in STATES
    (target / "PROTOCOL_INSTALLATION.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="+")
    args = parser.parse_args()
    if not PROTOCOL.exists() or not METADATA.exists():
        raise SystemExit("Canonical protocol artifacts are missing")
    results = [install(Path(raw)) for raw in args.targets]
    print(json.dumps({"status": "PASS", "protocol_sha256": digest(PROTOCOL), "results": results}, indent=2))


if __name__ == "__main__":
    main()
