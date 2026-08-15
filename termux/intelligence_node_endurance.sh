#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
NODE="$REPO_ROOT/termux/intelligence_node.sh"
SUPERVISOR="$REPO_ROOT/termux/intelligence_controller_supervisor.sh"
WORKER="$REPO_ROOT/termux/intelligence_controller_github_worker_once.sh"
SAMPLES="${CENTINAL26_ENDURANCE_SAMPLES:-61}"
INTERVAL="${CENTINAL26_ENDURANCE_INTERVAL:-60}"
MIN_SECONDS="${CENTINAL26_ENDURANCE_MIN_SECONDS:-3500}"
RECOVERY_SAMPLE="${CENTINAL26_ENDURANCE_RECOVERY_SAMPLE:-10}"
OUT="$GATE_ROOT/endurance_samples.jsonl"
REPORT="$GATE_ROOT/endurance_report.json"
RECOVERY_LOG="$GATE_ROOT/endurance_recovery.log"
DENIAL_LOG="$GATE_ROOT/endurance_denial.log"

mkdir -p "$GATE_ROOT"
: > "$OUT"

case "${PREFIX:-}" in
  */com.termux/*) ;;
  *) echo "BLOCKED: endurance qualification requires real Termux on Android" >&2; exit 10 ;;
esac

for n in "$SAMPLES" "$INTERVAL" "$MIN_SECONDS" "$RECOVERY_SAMPLE"; do
  case "$n" in (*[!0-9]*|'') echo "invalid numeric endurance setting" >&2; exit 64 ;; esac
done
[ "$SAMPLES" -ge 61 ] || { echo "BLOCKED: GA endurance requires at least 61 samples" >&2; exit 11; }
[ "$INTERVAL" -ge 60 ] || { echo "BLOCKED: GA endurance interval must be at least 60 seconds" >&2; exit 12; }
[ "$MIN_SECONDS" -ge 3500 ] || { echo "BLOCKED: GA endurance window must be at least 3500 seconds" >&2; exit 13; }

boot_id() {
  if [ -r /proc/sys/kernel/random/boot_id ]; then cat /proc/sys/kernel/random/boot_id; else awk '$1=="btime" {print "btime:"$2}' /proc/stat; fi
}

start_epoch="$(date +%s)"
start_boot="$(boot_id)"
unhealthy=0
recovery_pass=false
denial_pass=false

set +e
"$WORKER" --validate-command "automation.unsupported.probe" > "$DENIAL_LOG" 2>&1
denial_rc=$?
set -e
if [ "$denial_rc" -eq 65 ] && grep -q 'DENIED_UNSUPPORTED_COMMAND' "$DENIAL_LOG"; then denial_pass=true; fi

for ((i=1; i<=SAMPLES; i++)); do
  if [ "$i" -eq "$RECOVERY_SAMPLE" ]; then
    printf '%s stopping controller for bounded watchdog recovery drill\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RECOVERY_LOG"
    CENTINAL26_REPO_ROOT="$REPO_ROOT" "$SUPERVISOR" stop >> "$RECOVERY_LOG" 2>&1 || true
    recovered=false
    for _ in $(seq 1 18); do
      sleep 5
      probe="$("$NODE" status 2>/dev/null || echo '{}')"
      if [ "$(jq -r '.controller.controller_alive // false' <<<"$probe")" = "true" ]; then recovered=true; break; fi
    done
    recovery_pass="$recovered"
  fi

  status="$("$NODE" status 2>/dev/null || echo '{}')"
  current_boot="$(boot_id)"
  node_alive="$(jq -r '.process.node_alive // false' <<<"$status")"
  controller_alive="$(jq -r '.controller.controller_alive // false' <<<"$status")"
  chain_valid="$(jq -r '.controller.controller.event_chain_valid // false' <<<"$status")"
  hb="$(jq -r '.controller.heartbeat.observed_at // empty' <<<"$status")"
  healthy=true
  [ "$current_boot" = "$start_boot" ] || healthy=false
  [ "$node_alive" = "true" ] || healthy=false
  [ "$controller_alive" = "true" ] || healthy=false
  [ "$chain_valid" = "true" ] || healthy=false
  [ -n "$hb" ] || healthy=false
  [ "$healthy" = "true" ] || unhealthy=$((unhealthy + 1))
  jq -nc \
    --argjson sample "$i" \
    --arg observed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg boot_id "$current_boot" \
    --argjson healthy "$healthy" \
    --argjson status "$status" \
    '{sample:$sample,observed_at:$observed_at,boot_id:$boot_id,healthy:$healthy,status:$status}' >> "$OUT"
  if [ "$i" -lt "$SAMPLES" ]; then sleep "$INTERVAL"; fi
done

end_epoch="$(date +%s)"
elapsed=$((end_epoch - start_epoch))
samples_sha="$(sha256sum "$OUT" | awk '{print $1}')"
pass=false
if [ "$unhealthy" -eq 0 ] && [ "$elapsed" -ge "$MIN_SECONDS" ] && [ "$recovery_pass" = "true" ] && [ "$denial_pass" = "true" ] && [ "$(boot_id)" = "$start_boot" ]; then
  pass=true
fi

jq -n \
  --arg schema "centinal26.android_endurance/v1" \
  --arg status "$( [ "$pass" = true ] && echo PASS || echo FAIL )" \
  --arg observed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg boot_id "$start_boot" \
  --arg samples_sha256 "$samples_sha" \
  --argjson samples "$SAMPLES" \
  --argjson interval_seconds "$INTERVAL" \
  --argjson minimum_seconds "$MIN_SECONDS" \
  --argjson elapsed_seconds "$elapsed" \
  --argjson unhealthy_samples "$unhealthy" \
  --argjson recovery_drill_pass "$recovery_pass" \
  --argjson unsupported_command_denied "$denial_pass" \
  '{schema:$schema,status:$status,observed_at:$observed_at,platform:"android/termux",physical_android_validated:true,boot_id:$boot_id,samples:$samples,interval_seconds:$interval_seconds,minimum_seconds:$minimum_seconds,elapsed_seconds:$elapsed_seconds,unhealthy_samples:$unhealthy_samples,recovery_drill_pass:$recovery_drill_pass,unsupported_command_denied:$unsupported_command_denied,samples_sha256:$samples_sha256}' \
  > "$REPORT.tmp"
mv "$REPORT.tmp" "$REPORT"
cat "$REPORT"
[ "$pass" = true ]
