#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

FROST_ROOT="${FROST_ROOT:-$HOME/frost}"
REPO="${CENTINAL26_ROOT:-$FROST_ROOT/centinal26}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/frost-autopilot"
mkdir -p "$STATE_DIR"
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$STATE_DIR/autopilot.log"; }
[ -d "$REPO/.git" ] || { log "BLOCKED_LOCAL reason=centinal26_missing repo=$REPO"; exit 2; }
cd "$REPO"
[ -f automation/PROJECT_STATE.json ] || { log "BLOCKED_CANON reason=PROJECT_STATE_missing"; exit 3; }
[ -f automation/TERMUX_EXECUTION_PLANE.json ] || { log "BLOCKED_CANON reason=TERMUX_EXECUTION_PLANE_missing"; exit 3; }
python - <<'PY'
import json
from pathlib import Path
for p in ("automation/PROJECT_STATE.json", "automation/TERMUX_EXECUTION_PLANE.json"):
    json.loads(Path(p).read_text())
print("CANON_STATE_PARSE_PASS")
PY
ran=0
if [ -d /data/data/com.termux/files/usr ] && [ -f deploy/termux/library_cleaner/install_autopilot.sh ]; then
  log "RUN_CANONICAL_TERMUX_AUTOPILOT installer=deploy/termux/library_cleaner/install_autopilot.sh"
  rc=0
  bash deploy/termux/library_cleaner/install_autopilot.sh >>"$STATE_DIR/autopilot.log" 2>&1 || rc=$?
  case "$rc" in 0|2|20|22) ;; *) log "AUTOPILOT_DEGRADED rc=$rc" ;; esac
  ran=1
elif [ -d /data/data/com.termux/files/usr ] && [ -f deploy/termux/physical_boundary_solver/run.sh ]; then
  log "RUN_PHYSICAL_BOUNDARY_ENTRYPOINT path=deploy/termux/physical_boundary_solver/run.sh"
  rc=0
  bash deploy/termux/physical_boundary_solver/run.sh --resume >>"$STATE_DIR/autopilot.log" 2>&1 || rc=$?
  case "$rc" in 0|2|20|22) ;; *) log "PHYSICAL_BOUNDARY_DEGRADED rc=$rc" ;; esac
  ran=1
fi
if [ "$ran" -eq 0 ]; then
  for p in automation/autopilot.py automation/controller/autopilot.py automation/controller/controller.py automation/execution/autopilot.py; do
    if [ -f "$p" ]; then
      log "RUN_ENTRYPOINT path=$p"
      python "$p" --once 2>>"$STATE_DIR/autopilot.log" || python "$p" 2>>"$STATE_DIR/autopilot.log" || true
      ran=1
      break
    fi
  done
fi
[ "$ran" -ne 0 ] || log "NO_DISCOVERED_ENTRYPOINT canonical_state_available=true"
if [ -d openquest/tests ]; then
  python -m unittest discover -s openquest/tests -q
  python -m openquest.cli options >/dev/null
  log "OPENQUEST_SMOKE_PASS sha=$(git rev-parse HEAD)"
fi
log "AUTOPILOT_PULSE_COMPLETE sha=$(git rev-parse HEAD)"
