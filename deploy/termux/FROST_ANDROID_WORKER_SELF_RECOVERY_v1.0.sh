#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="1.0.0"
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
STATE="${FROST_WORKER_RECOVERY_STATE:-$HOME/.local/state/centinal26/worker-recovery}"
INTERVAL="${FROST_WORKER_RECOVERY_INTERVAL:-300}"
MODE="${1:---once}"
BOOTSTRAP_REL="deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh"
BOOTSTRAP="$REPO/$BOOTSTRAP_REL"
CFG="$ROOT/bridge.env"
START="$ROOT/bin/fleet-worker-start"
PIDFILE="$ROOT/state/fleet_worker.pid"
LOG="$STATE/recovery.log"
STATUS_JSON="$STATE/status.json"

mkdir -p "$STATE" "$HOME/.termux/boot" "$HOME/.local/bin"
chmod 700 "$STATE" 2>/dev/null || true

log(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }
write_status(){
  local state="$1" detail="$2"
  python - "$STATUS_JSON" "$state" "$detail" "$VERSION" <<'PY'
import json,pathlib,sys,datetime
p=pathlib.Path(sys.argv[1])
data={"schema":"frost-android-worker-self-recovery/v1","state":sys.argv[2],"detail":sys.argv[3],"version":sys.argv[4],"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
t=p.with_suffix('.tmp'); t.write_text(json.dumps(data,sort_keys=True)+"\n"); t.replace(p)
PY
  chmod 600 "$STATUS_JSON" 2>/dev/null || true
}

is_termux(){ case "${PREFIX:-}" in *com.termux*) return 0;; *) return 1;; esac; }
worker_running(){
  [[ -f "$PIDFILE" ]] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}
repo_trusted(){
  [[ -d "$REPO/.git" && -f "$BOOTSTRAP" ]] || return 1
  [[ -z "$(git -C "$REPO" status --porcelain -- "$BOOTSTRAP_REL" 2>/dev/null)" ]] || return 1
  local local_sha tracked_sha
  local_sha="$(sha256sum "$BOOTSTRAP" | awk '{print $1}')"
  tracked_sha="$(git -C "$REPO" show "HEAD:$BOOTSTRAP_REL" 2>/dev/null | sha256sum | awk '{print $1}')"
  [[ -n "$tracked_sha" && "$local_sha" == "$tracked_sha" ]]
}
has_noninteractive_auth(){
  [[ -s "$CFG" ]] && return 0
  [[ -n "${BASE44_TOKEN:-}" && -n "${BASE44_WORKER_EMAIL:-${BASE44_EMAIL:-}}" ]] && return 0
  [[ -n "${BASE44_PASSWORD:-}" && -n "${BASE44_EMAIL:-}" ]] && return 0
  return 1
}
start_existing_worker(){
  [[ -x "$START" && -s "$CFG" ]] || return 1
  "$START" >>"$LOG" 2>&1 || return 1
  sleep 1
  worker_running
}
install_or_repair_worker(){
  repo_trusted || { log 'bootstrap source failed trusted-repository check'; return 31; }
  has_noninteractive_auth || return 20
  log "running bounded canonical worker bootstrap $BOOTSTRAP_REL"
  bash "$BOOTSTRAP" </dev/null >>"$LOG" 2>&1 || return 32
  worker_running || return 33
}
recover_once(){
  is_termux || { write_status "NOT_TERMUX" "physical Android/Termux runtime required"; return 40; }
  if worker_running; then
    write_status "RUNNING" "bounded Android/Termux worker process healthy"
    return 0
  fi
  log 'worker not running; attempting bounded recovery'
  if start_existing_worker; then
    write_status "RECOVERED" "restarted existing authenticated worker"
    return 0
  fi
  if install_or_repair_worker; then
    write_status "RECOVERED" "installed/repaired worker from trusted canonical bootstrap"
    return 0
  fi
  rc=$?
  case "$rc" in
    20) write_status "AUTH_REQUIRED" "no reusable local Base44 worker credential source found" ;;
    31) write_status "SOURCE_UNTRUSTED" "canonical bootstrap identity could not be verified" ;;
    32|33) write_status "RECOVERY_FAILED" "bounded worker bootstrap/start failed; inspect recovery log" ;;
    *) write_status "RECOVERY_FAILED" "unexpected recovery failure rc=$rc" ;;
  esac
  return "$rc"
}
install_watchdog(){
  local self="$HOME/.local/bin/frost-android-worker-self-recovery"
  cp "$0" "$self"
  chmod 700 "$self"
  cat > "$HOME/.termux/boot/frost-android-worker-self-recovery.sh" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
sleep 25
if ! pgrep -f "$HOME/.local/bin/frost-android-worker-self-recovery --loop" >/dev/null 2>&1; then
  nohup "$HOME/.local/bin/frost-android-worker-self-recovery" --loop >/dev/null 2>&1 &
fi
SH
  chmod 700 "$HOME/.termux/boot/frost-android-worker-self-recovery.sh"
  write_status "INSTALLED" "boot-persistent bounded worker recovery installed"
}
self_test(){
  grep -q 'system.health' "$BOOTSTRAP" 2>/dev/null || true
  [[ "$BOOTSTRAP_REL" == "deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh" ]]
  [[ "$INTERVAL" =~ ^[0-9]+$ ]]
  (( INTERVAL >= 60 ))
  printf 'SELF_TEST PASS\n'
}

case "$MODE" in
  --once) recover_once ;;
  --loop) while :; do recover_once || true; sleep "$INTERVAL"; done ;;
  --install) is_termux || { write_status "NOT_TERMUX" "installation requires Termux"; exit 40; }; install_watchdog; recover_once || true ;;
  --status) [[ -s "$STATUS_JSON" ]] && cat "$STATUS_JSON" || printf '{"state":"UNKNOWN"}\n' ;;
  --self-test) self_test ;;
  --version) printf '%s\n' "$VERSION" ;;
  *) printf 'usage: %s [--once|--loop|--install|--status|--self-test|--version]\n' "$0" >&2; exit 2 ;;
esac
