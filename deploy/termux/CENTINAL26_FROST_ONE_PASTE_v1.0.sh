#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

INSTALLER_VERSION="1.0.0"
PINNED_COMMIT="06e05e9c85c4449443e0424640cd6198cd1493a9"
REPOSITORY_URL="https://github.com/12ephods-source/centinal26.git"
RESPONSE_OPENING='Yes, I would be happy to help you with that request.'

INSTALL_ROOT="${CENTINAL26_INSTALL_ROOT:-$HOME/.local/share/centinal26}"
BIN_DIR="${CENTINAL26_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${CENTINAL26_CONFIG_DIR:-$HOME/.config/centinal26}"
STATE_DIR="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
SOURCE_DIR="$INSTALL_ROOT/source-$PINNED_COMMIT"
VALIDATION_DIR="$INSTALL_ROOT/validation/$(date -u +%Y%m%dT%H%M%SZ)"

log() {
  printf '[centinal26-frost] %s\n' "$*"
}

fail() {
  printf '[centinal26-frost] ERROR: %s\n' "$*" >&2
  exit 1
}

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$CONFIG_DIR" "$STATE_DIR" "$VALIDATION_DIR"

if ! command -v python >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  command -v pkg >/dev/null 2>&1 || fail "python/git missing and this is not a Termux pkg environment"
  log "Installing required Termux packages: python git"
  if ! pkg install -y python git; then
    cat >&2 <<'EOF'
[centinal26-frost] Package installation failed.
[centinal26-frost] Do not bypass repository signature verification.
[centinal26-frost] If Termux reports an obsolete mirror or missing signing key, update
[centinal26-frost] Termux/repository configuration from an official Termux distribution,
[centinal26-frost] then rerun this installer.
EOF
    exit 20
  fi
fi

python - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python >=3.11 required; found {sys.version.split()[0]}")
PY

source_override="${CENTINAL26_SOURCE_DIR:-}"
if [[ -n "$source_override" ]]; then
  [[ -d "$source_override/.git" ]] || fail "CENTINAL26_SOURCE_DIR is not a Git checkout"
  actual="$(git -C "$source_override" rev-parse HEAD)"
  [[ "$actual" == "$PINNED_COMMIT" ]] || fail "source override HEAD $actual != pinned $PINNED_COMMIT"
  [[ -z "$(git -C "$source_override" status --porcelain --untracked-files=all)" ]] || \
    fail "source override is not clean; refusing mutable execution source"
  SOURCE_DIR="$(cd "$source_override" && pwd)"
elif [[ -d "$SOURCE_DIR/.git" ]] && \
     [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)" == "$PINNED_COMMIT" ]] && \
     [[ -z "$(git -C "$SOURCE_DIR" status --porcelain --untracked-files=all)" ]]; then
  log "Reusing verified pinned source checkout"
else
  if [[ -e "$SOURCE_DIR" ]]; then
    SOURCE_DIR="$INSTALL_ROOT/source-$PINNED_COMMIT-recovery-$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  log "Fetching pinned Centinal26 source"
  mkdir -p "$SOURCE_DIR"
  git -C "$SOURCE_DIR" init -q
  git -C "$SOURCE_DIR" remote add origin "$REPOSITORY_URL"
  git -C "$SOURCE_DIR" fetch -q --depth 1 origin "$PINNED_COMMIT"
  git -C "$SOURCE_DIR" checkout -q --detach FETCH_HEAD
fi

actual="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
[[ "$actual" == "$PINNED_COMMIT" ]] || fail "source HEAD $actual != pinned $PINNED_COMMIT"
[[ -z "$(git -C "$SOURCE_DIR" status --porcelain --untracked-files=all)" ]] || \
  fail "pinned source tree is not clean"

cat > "$CONFIG_DIR/RESPONSE_OPENING_POLICY.txt" <<EOF
$RESPONSE_OPENING
EOF

cat > "$CONFIG_DIR/INSTALL_POLICY.json" <<EOF
{
  "schema_version": 1,
  "installer_version": "$INSTALLER_VERSION",
  "repository": "$REPOSITORY_URL",
  "pinned_commit": "$PINNED_COMMIT",
  "execution_source": "$SOURCE_DIR",
  "default_state_dir": "$STATE_DIR",
  "response_opening": "$RESPONSE_OPENING",
  "runtime_model": "verified_git_pin_plus_pythonpath",
  "boot_autopilot_default": false
}
EOF

cat > "$BIN_DIR/centinal26-pinned-python" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
SOURCE_DIR='$SOURCE_DIR'
PINNED_COMMIT='$PINNED_COMMIT'
actual="\$(git -C "\$SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)"
[[ "\$actual" == "\$PINNED_COMMIT" ]] || {
  echo "Centinal26 source pin mismatch: \$actual" >&2
  exit 74
}
[[ -z "\$(git -C "\$SOURCE_DIR" status --porcelain --untracked-files=all)" ]] || {
  echo "Centinal26 source tree is dirty; refusing execution" >&2
  exit 75
}
export PYTHONPATH="\$SOURCE_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec python -S "\$@"
EOF
chmod 700 "$BIN_DIR/centinal26-pinned-python"

cat > "$BIN_DIR/centinal26" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
: "\${CENTINAL26_HOME:=$STATE_DIR}"
export CENTINAL26_HOME
exec '$BIN_DIR/centinal26-pinned-python' -m centinal26.cli "\$@"
EOF
chmod 700 "$BIN_DIR/centinal26"

cat > "$BIN_DIR/frost" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
: "\${CENTINAL26_HOME:=$STATE_DIR}"
export CENTINAL26_HOME
exec '$BIN_DIR/centinal26-pinned-python' -m centinal26.frost_cli "\$@"
EOF
chmod 700 "$BIN_DIR/frost"

cat > "$BIN_DIR/frost-safe-autopilot" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
max_tasks="\${CENTINAL26_SAFE_MAX_TASKS:-100}"
exec '$BIN_DIR/frost' autopilot --max-tasks "\$max_tasks"
EOF
chmod 700 "$BIN_DIR/frost-safe-autopilot"

cat > "$BIN_DIR/frost-doctor" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
'$BIN_DIR/frost' verify
'$BIN_DIR/frost' 'project state'
'$BIN_DIR/frost' criticize
'$BIN_DIR/frost' automate
EOF
chmod 700 "$BIN_DIR/frost-doctor"

log "Compiling pinned Python sources"
PYTHONPATH="$SOURCE_DIR/src" python -S -m compileall -q "$SOURCE_DIR/src"

EMPTY_STATE="$VALIDATION_DIR/empty-state"
SAFE_STATE="$VALIDATION_DIR/safe-state"
AUTH_STATE="$VALIDATION_DIR/auth-state"
mkdir -p "$EMPTY_STATE" "$SAFE_STATE" "$AUTH_STATE"

log "Running read-only CLI smoke checks"
CENTINAL26_HOME="$EMPTY_STATE" "$BIN_DIR/frost" 'project state' > "$VALIDATION_DIR/state.json"
CENTINAL26_HOME="$EMPTY_STATE" "$BIN_DIR/frost" verify > "$VALIDATION_DIR/verify.json"
CENTINAL26_HOME="$EMPTY_STATE" "$BIN_DIR/frost" criticize > "$VALIDATION_DIR/critique.json"
CENTINAL26_HOME="$EMPTY_STATE" "$BIN_DIR/frost" automate > "$VALIDATION_DIR/automate.json"

log "Running AUTO_SAFE physical execution smoke check"
CENTINAL26_HOME="$SAFE_STATE" "$BIN_DIR/centinal26-pinned-python" - <<'PY'
from pathlib import Path
import os
from centinal26.event_state import EventStore

home = Path(os.environ["CENTINAL26_HOME"])
store = EventStore(home / "events.sqlite3")
store.append(
    "TASK_CREATED",
    {
        "task_id": "device-safe-smoke",
        "objective": "device safe smoke",
        "capability": "system.echo",
        "input": {"probe": "termux"},
    },
    entity_id="device-safe-smoke",
)
store.close()
PY
CENTINAL26_HOME="$SAFE_STATE" "$BIN_DIR/frost" 'fix everything' > "$VALIDATION_DIR/safe-repair.json"
CENTINAL26_HOME="$SAFE_STATE" "$BIN_DIR/centinal26-pinned-python" - <<'PY'
from pathlib import Path
import os
from centinal26.event_state import EventStore, rebuild_state

home = Path(os.environ["CENTINAL26_HOME"])
store = EventStore(home / "events.sqlite3")
state = rebuild_state(store.events())
store.close()
assert state.tasks["device-safe-smoke"]["status"] == "COMPLETE"
PY

log "Running explicit-authorization boundary smoke check"
CENTINAL26_HOME="$AUTH_STATE" "$BIN_DIR/centinal26-pinned-python" - <<'PY'
from pathlib import Path
import os
from centinal26.event_state import EventStore

home = Path(os.environ["CENTINAL26_HOME"])
store = EventStore(home / "events.sqlite3")
store.append(
    "TASK_CREATED",
    {
        "task_id": "device-auth-smoke",
        "objective": "device authorization smoke",
        "capability": "system.echo",
        "input": {"probe": "termux"},
        "authority": "authorization_required",
    },
    entity_id="device-auth-smoke",
)
store.close()
PY
set +e
CENTINAL26_HOME="$AUTH_STATE" "$BIN_DIR/frost" 'fix everything' > "$VALIDATION_DIR/auth-repair.json"
auth_rc=$?
set -e
[[ "$auth_rc" -eq 3 ]] || fail "authorization boundary smoke expected exit 3, got $auth_rc"
CENTINAL26_HOME="$AUTH_STATE" "$BIN_DIR/centinal26-pinned-python" - <<'PY'
from pathlib import Path
import os
from centinal26.event_state import EventStore, rebuild_state

home = Path(os.environ["CENTINAL26_HOME"])
store = EventStore(home / "events.sqlite3")
events = store.events()
state = rebuild_state(events)
store.close()
assert state.tasks["device-auth-smoke"]["status"] == "DISCOVERED"
assert not any(event.type == "TASK_STARTED" for event in events)
assert any(
    event.type == "BLOCKER_RECORDED"
    and event.payload.get("reason") == "APPROVAL_REQUIRED"
    for event in events
)
PY

if [[ "${CENTINAL26_ENABLE_BOOT_AUTOPILOT:-0}" == "1" ]]; then
  BOOT_DIR="$HOME/.termux/boot"
  mkdir -p "$BOOT_DIR"
  cat > "$BOOT_DIR/centinal26-safe-autopilot" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -u
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
'$BIN_DIR/frost-safe-autopilot' >> '$STATE_DIR/boot-autopilot.log' 2>&1 || true
EOF
  chmod 700 "$BOOT_DIR/centinal26-safe-autopilot"
  log "Installed opt-in Termux:Boot safe-autopilot hook"
fi

python - "$VALIDATION_DIR" "$SOURCE_DIR" "$PINNED_COMMIT" "$INSTALLER_VERSION" <<'PY'
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

validation = Path(sys.argv[1])
source = Path(sys.argv[2])
pin = sys.argv[3]
version = sys.argv[4]
files = sorted(path for path in validation.iterdir() if path.is_file())
manifest = {
    "schema_version": 1,
    "installer_version": version,
    "pinned_commit": pin,
    "source_dir": str(source),
    "validated_at": datetime.now(UTC).isoformat(),
    "status": "DEVICE_INSTALL_SMOKE_PASS",
    "gates": {
        "source_pin": "PASS",
        "source_clean": "PASS",
        "python_compile": "PASS",
        "state_read": "PASS",
        "event_chain_verify": "PASS",
        "critique": "PASS",
        "automation_candidate_projection": "PASS",
        "auto_safe_execution": "PASS",
        "explicit_authorization_boundary": "PASS",
    },
    "evidence": [
        {
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in files
    ],
    "not_claimed": [
        "reboot_persistence",
        "long-duration_endurance",
        "remote_phone_worker_end_to_end",
        "autonomous_external_side_effects",
    ],
}
(validation / "INSTALL_RECEIPT.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

log "Installation and device smoke validation complete"
log "Pinned commit: $PINNED_COMMIT"
log "Source: $SOURCE_DIR"
log "State: $STATE_DIR"
log "Evidence: $VALIDATION_DIR"
log "Commands: frost | centinal26 | frost-safe-autopilot | frost-doctor"
log "Response opening policy: $CONFIG_DIR/RESPONSE_OPENING_POLICY.txt"
log "No reboot-persistence or external-effect autonomy claim is made by this installer."
