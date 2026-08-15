#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
VENV="${CENTINAL26_VENV:-$REPO_ROOT/.venv}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
PIDFILE="$GATE_ROOT/controller.pid"
LOGFILE="$GATE_ROOT/controller.log"
HEARTBEAT="$GATE_ROOT/heartbeat.json"
BOOT_EVIDENCE="$GATE_ROOT/boot_evidence.json"
POLL="${CENTINAL26_INTELLIGENCE_POLL:-10}"
TIMEZONE="${CENTINAL26_TIMEZONE:-America/Mexico_City}"

mkdir -p "$GATE_ROOT" "$STATE_ROOT"
chmod 700 "$GATE_ROOT" "$STATE_ROOT" 2>/dev/null || true

boot_id() {
  if [ -r /proc/sys/kernel/random/boot_id ]; then
    cat /proc/sys/kernel/random/boot_id
  else
    local btime
    btime="$(awk '$1 == "btime" {print $2}' /proc/stat 2>/dev/null || true)"
    [ -n "$btime" ] || btime="unknown"
    printf 'btime:%s\n' "$btime"
  fi
}

now_iso() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

controller_bin() {
  local bin="$VENV/bin/centinal26-intelligence"
  [ -x "$bin" ] || {
    echo "BLOCKED: controller executable missing at $bin" >&2
    exit 2
  }
  printf '%s\n' "$bin"
}

pid_alive() {
  local pid=""
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_heartbeat() {
  local origin="${1:-manual}" pid="" alive=false
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if pid_alive; then alive=true; fi
  jq -n \
    --arg observed_at "$(now_iso)" \
    --arg boot_id "$(boot_id)" \
    --arg device_id "${AUTOMATION_DEVICE_ID:-android-$(uname -m)}" \
    --arg platform "android/termux" \
    --arg origin "$origin" \
    --arg pid "$pid" \
    --argjson alive "$alive" \
    '{schema:"centinal26.worker_heartbeat/v1",observed_at:$observed_at,boot_id:$boot_id,device_id:$device_id,platform:$platform,origin:$origin,pid:$pid,controller_alive:$alive}' \
    > "$HEARTBEAT.tmp"
  mv "$HEARTBEAT.tmp" "$HEARTBEAT"
}

start_controller() {
  local bin
  bin="$(controller_bin)"
  if pid_alive; then
    write_heartbeat already-running
    return 0
  fi
  rm -f "$PIDFILE"
  nohup env \
    CENTINAL26_HOME="$STATE_ROOT" \
    CENTINAL26_TIMEZONE="$TIMEZONE" \
    "$bin" daemon --poll "$POLL" >> "$LOGFILE" 2>&1 </dev/null &
  local pid=$!
  printf '%s\n' "$pid" > "$PIDFILE"
  sleep 2
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "FAIL: controller daemon exited during startup" >&2
    tail -n 80 "$LOGFILE" >&2 2>/dev/null || true
    rm -f "$PIDFILE"
    exit 3
  fi
  write_heartbeat start
}

stop_controller() {
  if pid_alive; then
    local pid
    pid="$(cat "$PIDFILE")"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
  write_heartbeat stop
}

status_controller() {
  local alive=false pid="" controller_status='{}'
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if pid_alive; then alive=true; fi
  if [ -x "$VENV/bin/centinal26-intelligence" ]; then
    controller_status="$(CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" "$VENV/bin/centinal26-intelligence" status 2>/dev/null || echo '{}')"
  fi
  jq -n \
    --arg boot_id "$(boot_id)" \
    --arg pid "$pid" \
    --argjson alive "$alive" \
    --argjson controller "$controller_status" \
    --slurpfile heartbeat <(cat "$HEARTBEAT" 2>/dev/null || echo '{}') \
    '{boot_id:$boot_id,pid:$pid,controller_alive:$alive,heartbeat:($heartbeat[0] // {}),controller:$controller}'
}

case "${1:-status}" in
  start)
    start_controller
    status_controller
    ;;
  boot)
    start_controller
    write_heartbeat boot
    status_controller > "$BOOT_EVIDENCE.tmp"
    mv "$BOOT_EVIDENCE.tmp" "$BOOT_EVIDENCE"
    cat "$BOOT_EVIDENCE"
    ;;
  heartbeat)
    write_heartbeat manual
    cat "$HEARTBEAT"
    ;;
  stop)
    stop_controller
    status_controller
    ;;
  restart)
    stop_controller
    start_controller
    status_controller
    ;;
  status)
    status_controller
    ;;
  *)
    echo "usage: $0 {start|boot|heartbeat|stop|restart|status}" >&2
    exit 64
    ;;
esac
