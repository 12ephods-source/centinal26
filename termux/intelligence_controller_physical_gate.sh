#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV="${CENTINAL26_VENV:-$REPO_ROOT/.venv}"
STATE_ROOT="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
SUPERVISOR="$REPO_ROOT/termux/intelligence_controller_supervisor.sh"
PRE_REPORT="$GATE_ROOT/pre_reboot.json"
POST_REPORT="$GATE_ROOT/post_reboot.json"
BOOT_SCRIPT="$HOME/.termux/boot/centinal26-intelligence-controller.sh"
TIMEZONE="${CENTINAL26_TIMEZONE:-America/Mexico_City}"
MODE="${1:---pre-reboot}"

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

require_termux() {
  case "${PREFIX:-}" in
    */com.termux/*) ;;
    *) echo "BLOCKED: this gate must run inside Termux on Android" >&2; exit 10 ;;
  esac
  command -v python >/dev/null
  command -v jq >/dev/null
  command -v git >/dev/null
}

install_controller() {
  if [ ! -d "$VENV" ]; then
    python -m venv "$VENV"
  fi
  "$VENV/bin/python" -m pip install -e "$REPO_ROOT" >/dev/null
  CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" "$VENV/bin/centinal26-intelligence" init >/dev/null
}

observe_event() {
  local source_key="$1" change_type="$2" severity="$3" evidence="$4"
  CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" \
    "$VENV/bin/centinal26-intelligence" observe PHYSICAL_GATE "$source_key" "$change_type" "$severity" --evidence "$evidence"
}

claim_complete_event() {
  local event_json="$1" claimer="$2" result_json="$3"
  local event_key work_key claim_json
  event_key="$(jq -r '.event.event_key // empty' <<<"$event_json")"
  [ -n "$event_key" ] || { echo "FAIL: observation did not produce an event" >&2; return 1; }
  work_key="event:$event_key"
  CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" cycle >/dev/null
  claim_json="$(CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" claim "$work_key" --claimer "$claimer" --lease-seconds 30)"
  [ "$(jq -r '.work.work_key // empty' <<<"$claim_json")" = "$work_key" ] || return 1
  CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" complete "$work_key" --result "$result_json" >/dev/null
}

prepare_boot() {
  mkdir -p "$HOME/.termux/boot"
  cat > "$BOOT_SCRIPT" <<EOF_BOOT
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
sleep 20
export CENTINAL26_REPO_ROOT="$REPO_ROOT"
export CENTINAL26_VENV="$VENV"
export CENTINAL26_HOME="$STATE_ROOT"
export CENTINAL26_TIMEZONE="$TIMEZONE"
export AUTOMATION_INTELLIGENCE_GATE_ROOT="$GATE_ROOT"
"$SUPERVISOR" boot >> "$GATE_ROOT/boot.log" 2>&1
EOF_BOOT
  chmod 700 "$BOOT_SCRIPT"
}

pre_reboot() {
  require_termux
  install_controller
  [ -x "$SUPERVISOR" ] || { echo "BLOCKED: missing supervisor $SUPERVISOR" >&2; exit 11; }

  local commit pre_boot device start_status hb1 hb2 event_json event_result
  commit="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  pre_boot="$(boot_id)"
  device="${AUTOMATION_DEVICE_ID:-android-$(uname -m)}"

  start_status="$(CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" start)"
  [ "$(jq -r '.controller_alive' <<<"$start_status")" = "true" ] || { echo "FAIL: daemon not alive" >&2; exit 12; }
  hb1="$(cat "$GATE_ROOT/heartbeat.json")"

  event_json="$(observe_event "$device-execution" STATE_CHANGE HIGH "$(jq -nc --arg t "$(now_iso)" --arg b "$pre_boot" --arg c "$commit" --arg d "$device" '{phase:"physical-pre-reboot",observed_at:$t,boot_id:$b,commit:$c,device_id:$d,platform:"android/termux"}')")"
  event_result="$(jq -nc --arg b "$pre_boot" --arg c "$commit" '{status:"PASS",gate:"physical-job-execution",boot_id:$b,commit:$c}')"
  claim_complete_event "$event_json" "$device" "$event_result" || { echo "FAIL: claim/complete gate" >&2; exit 13; }

  local lease_event lease_event_key lease_work first_claim second_claim
  lease_event="$(observe_event "$device-lease-recovery" NEW_EVIDENCE HIGH "$(jq -nc --arg t "$(now_iso)" --arg b "$pre_boot" '{phase:"lease-recovery",observed_at:$t,boot_id:$b}')")"
  lease_event_key="$(jq -r '.event.event_key // empty' <<<"$lease_event")"
  [ -n "$lease_event_key" ] || { echo "FAIL: lease observation did not produce an event" >&2; exit 14; }
  lease_work="event:$lease_event_key"
  first_claim="$(CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" claim "$lease_work" --claimer "$device-first" --lease-seconds 1)"
  [ "$(jq -r '.work.work_key // empty' <<<"$first_claim")" = "$lease_work" ] || { echo "FAIL: initial lease claim" >&2; exit 15; }
  sleep 2
  second_claim="$(CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" claim "$lease_work" --claimer "$device-recovery" --lease-seconds 30)"
  [ "$(jq -r '.work.claimed_by // empty' <<<"$second_claim")" = "$device-recovery" ] || { echo "FAIL: expired lease recovery" >&2; exit 16; }
  CENTINAL26_HOME="$STATE_ROOT" "$VENV/bin/centinal26-intelligence" complete "$lease_work" --result '{"status":"PASS","gate":"expired-lease-recovery"}' >/dev/null

  sleep 1
  CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" heartbeat >/dev/null
  hb2="$(cat "$GATE_ROOT/heartbeat.json")"
  [ "$(jq -r '.observed_at' <<<"$hb1")" != "$(jq -r '.observed_at' <<<"$hb2")" ] || { echo "FAIL: heartbeat did not advance" >&2; exit 17; }

  local status
  status="$(CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" "$VENV/bin/centinal26-intelligence" status)"
  [ "$(jq -r '.event_chain_valid' <<<"$status")" = "true" ] || { echo "FAIL: event chain invalid" >&2; exit 18; }

  prepare_boot
  jq -n \
    --arg schema "centinal26.intelligence_physical_gate/v1" \
    --arg phase "AWAITING_REBOOT" \
    --arg observed_at "$(now_iso)" \
    --arg pre_boot_id "$pre_boot" \
    --arg commit "$commit" \
    --arg device_id "$device" \
    --arg boot_script "$BOOT_SCRIPT" \
    --argjson controller_status "$status" \
    --argjson heartbeat "$hb2" \
    '{schema:$schema,phase:$phase,observed_at:$observed_at,pre_boot_id:$pre_boot_id,commit:$commit,device_id:$device_id,platform:"android/termux",job_execution:"PASS",lease_recovery:"PASS",heartbeat_advancement:"PASS",event_chain:"PASS",boot_script:$boot_script,controller_status:$controller_status,heartbeat:$heartbeat}' \
    > "$PRE_REPORT.tmp"
  mv "$PRE_REPORT.tmp" "$PRE_REPORT"
  cat "$PRE_REPORT"
  exit 20
}

post_reboot() {
  require_termux
  [ -f "$PRE_REPORT" ] || { echo "BLOCKED: no pre-reboot report" >&2; exit 30; }
  local pre_boot post_boot boot_evidence supervisor_status status heartbeat_age now hb_time
  pre_boot="$(jq -r '.pre_boot_id' "$PRE_REPORT")"
  post_boot="$(boot_id)"
  [ "$post_boot" != "$pre_boot" ] || { echo "BLOCKED: reboot not yet observed" >&2; exit 31; }
  [ -f "$GATE_ROOT/boot_evidence.json" ] || { echo "FAIL: Termux:Boot controller evidence missing" >&2; exit 32; }
  boot_evidence="$(cat "$GATE_ROOT/boot_evidence.json")"
  [ "$(jq -r '.boot_id' <<<"$boot_evidence")" = "$post_boot" ] || { echo "FAIL: boot evidence is not from current boot" >&2; exit 33; }
  [ "$(jq -r '.controller_alive' <<<"$boot_evidence")" = "true" ] || { echo "FAIL: controller did not return after boot" >&2; exit 34; }

  supervisor_status="$(CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" status)"
  [ "$(jq -r '.controller_alive' <<<"$supervisor_status")" = "true" ] || { echo "FAIL: controller is not alive post-reboot" >&2; exit 35; }
  status="$(CENTINAL26_HOME="$STATE_ROOT" CENTINAL26_TIMEZONE="$TIMEZONE" "$VENV/bin/centinal26-intelligence" status)"
  [ "$(jq -r '.event_chain_valid' <<<"$status")" = "true" ] || { echo "FAIL: event chain invalid post-reboot" >&2; exit 36; }

  CENTINAL26_REPO_ROOT="$REPO_ROOT" CENTINAL26_VENV="$VENV" CENTINAL26_HOME="$STATE_ROOT" "$SUPERVISOR" heartbeat >/dev/null
  now="$(date +%s)"
  hb_time="$(date -d "$(jq -r '.observed_at' "$GATE_ROOT/heartbeat.json")" +%s 2>/dev/null || echo 0)"
  heartbeat_age=$((now - hb_time))
  [ "$heartbeat_age" -ge 0 ] && [ "$heartbeat_age" -le 180 ] || { echo "FAIL: stale post-reboot heartbeat" >&2; exit 37; }

  local event_json result_json
  event_json="$(observe_event "${AUTOMATION_DEVICE_ID:-android-$(uname -m)}-post-reboot" NEW_EVIDENCE HIGH "$(jq -nc --arg t "$(now_iso)" --arg b "$post_boot" '{phase:"physical-post-reboot",observed_at:$t,boot_id:$b,controller_returned:true}')")"
  result_json="$(jq -nc --arg b "$post_boot" '{status:"PASS",gate:"post-reboot-return",boot_id:$b}')"
  claim_complete_event "$event_json" "${AUTOMATION_DEVICE_ID:-android-$(uname -m)}" "$result_json" || { echo "FAIL: post-reboot claim/complete" >&2; exit 38; }

  jq -n \
    --arg schema "centinal26.intelligence_physical_gate/v1" \
    --arg phase "PHYSICAL_VALIDATED" \
    --arg observed_at "$(now_iso)" \
    --arg pre_boot_id "$pre_boot" \
    --arg post_boot_id "$post_boot" \
    --argjson heartbeat_age "$heartbeat_age" \
    --argjson boot_evidence "$boot_evidence" \
    --argjson controller_status "$status" \
    '{schema:$schema,phase:$phase,observed_at:$observed_at,pre_boot_id:$pre_boot_id,post_boot_id:$post_boot,reboot_change:"PASS",boot_autostart:"PASS",controller_return:"PASS",post_reboot_job:"PASS",event_chain:"PASS",heartbeat_freshness:"PASS",heartbeat_age_seconds:$heartbeat_age,boot_evidence:$boot_evidence,controller_status:$controller_status}' \
    > "$POST_REPORT.tmp"
  mv "$POST_REPORT.tmp" "$POST_REPORT"
  cat "$POST_REPORT"
}

case "$MODE" in
  --pre-reboot) pre_reboot ;;
  --post-reboot) post_reboot ;;
  *) echo "usage: $0 [--pre-reboot|--post-reboot]" >&2; exit 64 ;;
esac
