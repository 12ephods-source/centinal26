#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
VENV="${CENTINAL26_VENV:-$REPO_ROOT/.venv}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
PIDFILE="$GATE_ROOT/controller.pid"
PIDSTART="$GATE_ROOT/controller.pidstart"
LOGFILE="$GATE_ROOT/controller.log"
HEARTBEAT="$GATE_ROOT/heartbeat.json"
HEARTBEAT_SEQ="$GATE_ROOT/heartbeat.seq"
BOOT_EVIDENCE="$GATE_ROOT/boot_evidence.json"
POLL="${CENTINAL26_INTELLIGENCE_POLL:-10}"
TIMEZONE="${CENTINAL26_TIMEZONE:-America/Mexico_City}"
LOG_MAX_BYTES="${CENTINAL26_LOG_MAX_BYTES:-1048576}"

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

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

controller_bin() {
  local bin="$VENV/bin/centinal26-intelligence"
  [ -x "$bin" ] || {
    echo "BLOCKED: controller executable missing at $bin" >&2
    exit 2
  }
  printf '%s\n' "$bin"
}

pid_start_ticks() {
  local pid="$1"
  [ -r "/proc/$pid/stat" ] || return 1
  awk '{print $22}' "/proc/$pid/stat"
}

pid_identity_ok() {
  local pid="$1" expected_start="${2:-}" actual_start="" cmdline=""
  kill -0 "$pid" 2>/dev/null || return 1
  actual_start="$(pid_start_ticks "$pid" 2>/dev/null || true)"
  [ -n "$actual_start" ] || return 1
  [ -z "$expected_start" ] || [ "$actual_start" = "$expected_start" ] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmdline" in
    *centinal26-intelligence*daemon*) return 0 ;;
    *) return 1 ;;
  esac
}

pid_alive() {
  local pid="" expected_start=""
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -f "$PIDSTART" ] && expected_start="$(cat "$PIDSTART" 2>/dev/null || true)"
  [ -n "$pid" ] && pid_identity_ok "$pid" "$expected_start"
}

repo_commit() {
  git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown\n'
}

next_heartbeat_seq() {
  local n=0
  [ -f "$HEARTBEAT_SEQ" ] && n="$(cat "$HEARTBEAT_SEQ" 2>/dev/null || echo 0)"
  case "$n" in (*[!0-9]*|'') n=0 ;; esac
  n=$((n + 1))
  printf '%s\n' "$n" > "$HEARTBEAT_SEQ.tmp"
  mv "$HEARTBEAT_SEQ.tmp" "$HEARTBEAT_SEQ"
  printf '%s\n' "$n"
}

rotate_log() {
  local size=0
  [ -f "$LOGFILE" ] || return 0
  size="$(wc -c < "$LOGFILE" 2>/dev/null || echo 0)"
  case "$size" in (*[!0-9]*|'') size=0 ;; esac
  if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
    rm -f "$LOGFILE.2"
    [ -f "$LOGFILE.1" ] && mv "$LOGFILE.1" "$LOGFILE.2"
    mv "$LOGFILE" "$LOGFILE.1"
  fi
}

write_heartbeat() {
  local origin="${1:-manual}" pid="" pidstart="" alive=false seq
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -f "$PIDSTART" ] && pidstart="$(cat "$PIDSTART" 2>/dev/null || true)"
  if pid_alive; then alive=true; fi
  seq="$(next_heartbeat_seq)"
  jq -n \
    --arg observed_at "$(now_iso)" \
    --arg boot_id "$(boot_id)" \
    --arg device_id "${AUTOMATION_DEVICE_ID:-android-$(uname -m)}" \
    --arg platform "android/termux" \
    --arg origin "$origin" \
    --arg pid "$pid" \
    --arg pid_start_ticks "$pidstart" \
    --arg repo_commit "$(repo_commit)" \
    --argjson sequence "$seq" \
    --argjson alive "$alive" \
    '{schema:"centinal26.worker_heartbeat/v2",observed_at:$observed_at,sequence:$sequence,boot_id:$boot_id,device_id:$device_id,platform:$platform,origin:$origin,pid:$pid,pid_start_ticks:$pid_start_ticks,repo_commit:$repo_commit,controller_alive:$alive}' \
    > "$HEARTBEAT.tmp"
  mv "$HEARTBEAT.tmp" "$HEARTBEAT"
}

start_controller() {
  local bin pid pidstart
  bin="$(controller_bin)"
  if pid_alive; then
    write_heartbeat already-running
    return 0
  fi
  rm -f "$PIDFILE" "$PIDSTART"
  rotate_log
  nohup env \
    CENTINAL26_HOME="$STATE_ROOT" \
    CENTINAL26_TIMEZONE="$TIMEZONE" \
    "$bin" daemon --poll "$POLL" >> "$LOGFILE" 2>&1 </dev/null &
  pid=$!
  printf '%s\n' "$pid" > "$PIDFILE"
  sleep 1
  pidstart="$(pid_start_ticks "$pid" 2>/dev/null || true)"
  [ -n "$pidstart" ] && printf '%s\n' "$pidstart" > "$PIDSTART"
  sleep 1
  if ! pid_alive; then
    echo "FAIL: controller daemon exited or identity check failed during startup" >&2
    tail -n 80 "$LOGFILE" >&2 2>/dev/null || true
    rm -f "$PIDFILE" "$PIDSTART"
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
      pid_identity_ok "$pid" "$(cat "$PIDSTART" 2>/dev/null || true)" || break
      sleep 1
    done
    pid_identity_ok "$pid" "$(cat "$PIDSTART" 2>/dev/null || true)" && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE" "$PIDSTART"
  write_heartbeat stop
}

status_controller() {
  local alive=false pid="" pidstart="" controller_status='{}'
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -f "$PIDSTART" ] && pidstart="$(cat "$PIDSTART" 2>/dev/null || true)"
  if pid_alive; then alive=true; fi
  if [ -x "$VENV/bin/centinal26-intelligence" ]; then
    controller_status="$(CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" "$VENV/bin/centinal26-intelligence" status 2>/dev/null || echo '{}')"
  fi
  jq -n \
    --arg boot_id "$(boot_id)" \
    --arg pid "$pid" \
    --arg pid_start_ticks "$pidstart" \
    --arg repo_commit "$(repo_commit)" \
    --argjson alive "$alive" \
    --argjson controller "$controller_status" \
    --slurpfile heartbeat <(cat "$HEARTBEAT" 2>/dev/null || echo '{}') \
    '{schema:"centinal26.controller_supervisor_status/v2",boot_id:$boot_id,pid:$pid,pid_start_ticks:$pid_start_ticks,repo_commit:$repo_commit,controller_alive:$alive,heartbeat:($heartbeat[0] // {}),controller:$controller}'
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
