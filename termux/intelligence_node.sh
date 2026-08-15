#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

NODE_VERSION="2.0.0"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
VENV="${CENTINAL26_VENV:-$REPO_ROOT/.venv}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
SUPERVISOR="$REPO_ROOT/termux/intelligence_controller_supervisor.sh"
WORKER="$REPO_ROOT/termux/intelligence_controller_github_worker_once.sh"
REPORTER="$REPO_ROOT/termux/intelligence_controller_report_after_reboot.sh"
NODE_PIDFILE="$GATE_ROOT/node.pid"
NODE_PIDSTART="$GATE_ROOT/node.pidstart"
NODE_LOG="$GATE_ROOT/node.log"
NODE_STATUS="$GATE_ROOT/node_status.json"
PRE_REPORT="$GATE_ROOT/pre_reboot.json"
POST_REPORT="$GATE_ROOT/post_reboot.json"
HEARTBEAT_INTERVAL="${CENTINAL26_NODE_HEARTBEAT_INTERVAL:-30}"
WORKER_INTERVAL="${CENTINAL26_NODE_WORKER_INTERVAL:-120}"
LOOP_INTERVAL="${CENTINAL26_NODE_LOOP_INTERVAL:-5}"
MAX_BACKOFF="${CENTINAL26_NODE_MAX_BACKOFF:-900}"
LOG_MAX_BYTES="${CENTINAL26_LOG_MAX_BYTES:-1048576}"

mkdir -p "$GATE_ROOT" "$STATE_ROOT"
chmod 700 "$GATE_ROOT" "$STATE_ROOT" 2>/dev/null || true

now_epoch() { date +%s; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

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

pid_start_ticks() {
  local pid="$1"
  [ -r "/proc/$pid/stat" ] || return 1
  awk '{print $22}' "/proc/$pid/stat"
}

node_pid_alive() {
  local pid="" expected="" actual="" cmdline=""
  [ -f "$NODE_PIDFILE" ] && pid="$(cat "$NODE_PIDFILE" 2>/dev/null || true)"
  [ -f "$NODE_PIDSTART" ] && expected="$(cat "$NODE_PIDSTART" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  actual="$(pid_start_ticks "$pid" 2>/dev/null || true)"
  [ -n "$actual" ] || return 1
  [ -z "$expected" ] || [ "$actual" = "$expected" ] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmdline" in
    *intelligence_node.sh*run*) return 0 ;;
    *) return 1 ;;
  esac
}

repo_commit() { git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown\n'; }
repo_branch() { git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf 'unknown\n'; }

repo_dirty_json() {
  if [ -d "$REPO_ROOT/.git" ] && [ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]; then
    printf 'true\n'
  else
    printf 'false\n'
  fi
}

disk_free_kb() {
  df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || echo 0
}

mem_available_kb() {
  awk '/^MemAvailable:/ {print $2; found=1} END {if(!found) print 0}' /proc/meminfo 2>/dev/null || echo 0
}

battery_percent() {
  local p
  for p in /sys/class/power_supply/battery/capacity /sys/class/power_supply/*/capacity; do
    [ -r "$p" ] && { cat "$p"; return 0; }
  done
  echo -1
}

battery_temp_tenths_c() {
  local p
  for p in /sys/class/power_supply/battery/temp /sys/class/power_supply/*/temp; do
    [ -r "$p" ] && { cat "$p"; return 0; }
  done
  echo -1
}

rotate_log() {
  local size=0
  [ -f "$NODE_LOG" ] || return 0
  size="$(wc -c < "$NODE_LOG" 2>/dev/null || echo 0)"
  case "$size" in (*[!0-9]*|'') size=0 ;; esac
  if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
    rm -f "$NODE_LOG.2"
    [ -f "$NODE_LOG.1" ] && mv "$NODE_LOG.1" "$NODE_LOG.2"
    mv "$NODE_LOG" "$NODE_LOG.1"
  fi
}

controller_status_json() {
  if [ -x "$SUPERVISOR" ]; then
    CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" status 2>/dev/null || echo '{}'
  else
    echo '{}'
  fi
}

write_status() {
  local origin="${1:-manual}" controller='{}' node_alive=false node_pid="" node_pidstart=""
  controller="$(controller_status_json)"
  [ -f "$NODE_PIDFILE" ] && node_pid="$(cat "$NODE_PIDFILE" 2>/dev/null || true)"
  [ -f "$NODE_PIDSTART" ] && node_pidstart="$(cat "$NODE_PIDSTART" 2>/dev/null || true)"
  if node_pid_alive; then node_alive=true; fi
  jq -n \
    --arg schema "centinal26.termux_node/v2" \
    --arg version "$NODE_VERSION" \
    --arg observed_at "$(now_iso)" \
    --arg origin "$origin" \
    --arg boot_id "$(boot_id)" \
    --arg device_id "${AUTOMATION_DEVICE_ID:-android-$(uname -m)}" \
    --arg repo_commit "$(repo_commit)" \
    --arg repo_branch "$(repo_branch)" \
    --arg node_pid "$node_pid" \
    --arg node_pid_start_ticks "$node_pidstart" \
    --argjson node_alive "$node_alive" \
    --argjson repo_dirty "$(repo_dirty_json)" \
    --argjson disk_free_kb "$(disk_free_kb)" \
    --argjson mem_available_kb "$(mem_available_kb)" \
    --argjson battery_percent "$(battery_percent)" \
    --argjson battery_temp_tenths_c "$(battery_temp_tenths_c)" \
    --argjson controller "$controller" \
    --arg pre_reboot "$( [ -f "$PRE_REPORT" ] && echo present || echo absent )" \
    --arg post_reboot "$( [ -f "$POST_REPORT" ] && echo present || echo absent )" \
    '{schema:$schema,node_version:$version,observed_at:$observed_at,origin:$origin,boot_id:$boot_id,device_id:$device_id,platform:"android/termux",repo:{commit:$repo_commit,branch:$repo_branch,dirty:$repo_dirty},process:{node_alive:$node_alive,node_pid:$node_pid,node_pid_start_ticks:$node_pid_start_ticks},resources:{disk_free_kb:$disk_free_kb,mem_available_kb:$mem_available_kb,battery_percent:$battery_percent,battery_temp_tenths_c:$battery_temp_tenths_c},physical_gate:{pre_reboot:$pre_reboot,post_reboot:$post_reboot},controller:$controller}' \
    > "$NODE_STATUS.tmp"
  mv "$NODE_STATUS.tmp" "$NODE_STATUS"
}

ensure_controller() {
  local status alive
  status="$(controller_status_json)"
  alive="$(jq -r '.controller_alive // false' <<<"$status" 2>/dev/null || echo false)"
  if [ "$alive" != "true" ]; then
    CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" start >/dev/null
    printf '%s controller_restarted\n' "$(now_iso)"
  fi
}

heartbeat_once() {
  CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" heartbeat >/dev/null
  write_status heartbeat
}

awaiting_same_boot_reboot() {
  [ -f "$PRE_REPORT" ] || return 1
  [ -f "$POST_REPORT" ] && return 1
  local pre current
  pre="$(jq -r '.pre_boot_id // empty' "$PRE_REPORT" 2>/dev/null || true)"
  current="$(boot_id)"
  [ -n "$pre" ] && [ "$pre" = "$current" ]
}

post_reboot_ready() {
  [ -f "$PRE_REPORT" ] || return 1
  [ -f "$POST_REPORT" ] && return 1
  local pre current
  pre="$(jq -r '.pre_boot_id // empty' "$PRE_REPORT" 2>/dev/null || true)"
  current="$(boot_id)"
  [ -n "$pre" ] && [ "$pre" != "$current" ]
}

worker_once() {
  if post_reboot_ready && [ -x "$REPORTER" ]; then
    "$REPORTER"
    return $?
  fi
  if awaiting_same_boot_reboot; then
    echo "AWAITING_REBOOT"
    return 0
  fi
  [ -x "$WORKER" ] || return 0
  "$WORKER"
}

run_loop() {
  local last_hb=0 last_worker=0 failures=0 backoff=0 now worker_due
  printf '%s\n' "$$" > "$NODE_PIDFILE"
  printf '%s\n' "$(pid_start_ticks "$$")" > "$NODE_PIDSTART"
  trap 'rm -f "$NODE_PIDFILE" "$NODE_PIDSTART"; exit 0' TERM INT EXIT
  ensure_controller
  heartbeat_once
  while :; do
    now="$(now_epoch)"
    if [ $((now - last_hb)) -ge "$HEARTBEAT_INTERVAL" ]; then
      if ensure_controller && heartbeat_once; then
        last_hb="$now"
      fi
    fi

    worker_due=$((WORKER_INTERVAL + backoff))
    if [ $((now - last_worker)) -ge "$worker_due" ]; then
      set +e
      worker_once >> "$NODE_LOG" 2>&1
      rc=$?
      set -e
      last_worker="$now"
      if [ "$rc" -eq 0 ]; then
        failures=0
        backoff=0
      else
        failures=$((failures + 1))
        backoff=$((2 ** (failures > 8 ? 8 : failures) * 5))
        [ "$backoff" -le "$MAX_BACKOFF" ] || backoff="$MAX_BACKOFF"
        printf '%s worker_rc=%s retry_backoff=%s\n' "$(now_iso)" "$rc" "$backoff" >> "$NODE_LOG"
      fi
      write_status worker
      rotate_log
    fi
    sleep "$LOOP_INTERVAL"
  done
}

start_node() {
  local pidstart
  if node_pid_alive; then
    write_status already-running
    cat "$NODE_STATUS"
    return 0
  fi
  rm -f "$NODE_PIDFILE" "$NODE_PIDSTART"
  rotate_log
  nohup "$0" run >> "$NODE_LOG" 2>&1 </dev/null &
  local pid=$!
  printf '%s\n' "$pid" > "$NODE_PIDFILE"
  sleep 1
  pidstart="$(pid_start_ticks "$pid" 2>/dev/null || true)"
  [ -n "$pidstart" ] && printf '%s\n' "$pidstart" > "$NODE_PIDSTART"
  sleep 1
  node_pid_alive || {
    echo "FAIL: node watchdog failed to start" >&2
    tail -n 80 "$NODE_LOG" >&2 2>/dev/null || true
    exit 3
  }
  write_status start
  cat "$NODE_STATUS"
}

stop_node() {
  local pid expected
  if node_pid_alive; then
    pid="$(cat "$NODE_PIDFILE")"
    expected="$(cat "$NODE_PIDSTART" 2>/dev/null || true)"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      node_pid_alive || break
      sleep 1
    done
    node_pid_alive && kill -9 "$pid" 2>/dev/null || true
    : "$expected"
  fi
  rm -f "$NODE_PIDFILE" "$NODE_PIDSTART"
  CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" stop >/dev/null 2>&1 || true
  write_status stop
  cat "$NODE_STATUS"
}

doctor() {
  local config_ok=false supervisor_ok=false worker_ok=false reporter_ok=false venv_ok=false boot_hook=false auth_mode="none"
  [ -f "$HOME/.automation_os_github/config" ] && config_ok=true
  [ -x "$SUPERVISOR" ] && supervisor_ok=true
  [ -x "$WORKER" ] && worker_ok=true
  [ -x "$REPORTER" ] && reporter_ok=true
  [ -x "$VENV/bin/centinal26-intelligence" ] && venv_ok=true
  [ -x "$HOME/.termux/boot/centinal26-intelligence-controller.sh" ] && boot_hook=true
  if [ -n "${GITHUB_TOKEN:-}" ]; then auth_mode="environment"; elif [ -f "$HOME/.automation_os_github/config" ]; then auth_mode="config"; fi
  write_status doctor
  jq \
    --argjson config_ok "$config_ok" \
    --argjson supervisor_ok "$supervisor_ok" \
    --argjson worker_ok "$worker_ok" \
    --argjson reporter_ok "$reporter_ok" \
    --argjson venv_ok "$venv_ok" \
    --argjson boot_hook "$boot_hook" \
    --arg auth_mode "$auth_mode" \
    '. + {doctor:{config_present:$config_ok,supervisor_present:$supervisor_ok,worker_present:$worker_ok,reporter_present:$reporter_ok,venv_ready:$venv_ok,termux_boot_hook_present:$boot_hook,github_auth_mode:$auth_mode}}' \
    "$NODE_STATUS"
}

safe_upgrade() {
  [ -d "$REPO_ROOT/.git" ] || { echo "BLOCKED: repository missing" >&2; exit 4; }
  [ "$(repo_dirty_json)" = "false" ] || { echo "BLOCKED: repository has local changes" >&2; exit 5; }
  local branch
  branch="$(repo_branch)"
  [ "$branch" = "main" ] || { echo "BLOCKED: explicit node upgrade requires main branch; found $branch" >&2; exit 6; }
  git -C "$REPO_ROOT" fetch origin main
  git -C "$REPO_ROOT" merge-base --is-ancestor HEAD origin/main || {
    echo "BLOCKED: local main diverged from origin/main; refusing non-fast-forward upgrade" >&2
    exit 7
  }
  git -C "$REPO_ROOT" merge --ff-only origin/main
  "$VENV/bin/python" -m pip install -e "$REPO_ROOT" >/dev/null
  "$0" restart
}

case "${1:-status}" in
  run) run_loop ;;
  start) start_node ;;
  boot)
    start_node >/dev/null
    heartbeat_once
    write_status boot
    cat "$NODE_STATUS"
    ;;
  kick)
    start_node >/dev/null
    set +e
    worker_once
    rc=$?
    set -e
    write_status kick
    exit "$rc"
    ;;
  heartbeat)
    start_node >/dev/null
    heartbeat_once
    cat "$NODE_STATUS"
    ;;
  status)
    write_status status
    cat "$NODE_STATUS"
    ;;
  doctor) doctor ;;
  stop) stop_node ;;
  restart)
    stop_node >/dev/null
    start_node
    ;;
  upgrade) safe_upgrade ;;
  *)
    echo "usage: $0 {start|boot|kick|heartbeat|status|doctor|stop|restart|upgrade}" >&2
    exit 64
    ;;
esac
