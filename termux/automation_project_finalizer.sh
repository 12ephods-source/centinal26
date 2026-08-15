#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
PHYSICAL_GATE="$REPO_ROOT/termux/intelligence_controller_physical_gate.sh"
ENDURANCE="$REPO_ROOT/termux/intelligence_node_endurance.sh"
VERIFIER="$REPO_ROOT/termux/verify_project_finalization.py"
RC4_RECOVERY="$REPO_ROOT/deploy/termux/recover-rc4-parent-inputs.sh"
RC4_ROOT="${FROST_RC4_PARENT_DIR:-$HOME/automation-rc4-parent-inputs}"
PRE_REPORT="$GATE_ROOT/project_pre_reboot.json"
FINAL_REPORT="$GATE_ROOT/project_final.json"
SYNC_REPORT="$GATE_ROOT/device_sync.json"
LOCKDIR="$GATE_ROOT/project_finalizer.lock"
MODE="${1:---pre-reboot}"

mkdir -p "$GATE_ROOT"
chmod 700 "$GATE_ROOT" 2>/dev/null || true

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha_file() { sha256sum "$1" | awk '{print $1}'; }

legacy_recovery() {
  local out="$GATE_ROOT/legacy_rc4_recovery.stdout.log"
  local err="$GATE_ROOT/legacy_rc4_recovery.stderr.log"
  local rc=127 status="NOT_RUN"
  if [ -f "$RC4_RECOVERY" ]; then
    set +e
    bash "$RC4_RECOVERY" >"$out" 2>"$err"
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ -f "$RC4_ROOT/PARENT_RECOVERY_REPORT.json" ]; then
      if [ "$(jq -r '.status // empty' "$RC4_ROOT/PARENT_RECOVERY_REPORT.json" 2>/dev/null)" = "PASS" ] \
        && [ "$(jq -r '.installers_executed // true' "$RC4_ROOT/PARENT_RECOVERY_REPORT.json" 2>/dev/null)" = "false" ]; then
        status="PASS"
      else
        status="REVIEW"
      fi
    else
      status="PENDING_HISTORICAL_ARTIFACTS"
    fi
  fi
  jq -n \
    --arg status "$status" \
    --argjson exit_code "$rc" \
    --arg report "$RC4_ROOT/PARENT_RECOVERY_REPORT.json" \
    --arg stdout "$out" \
    --arg stderr "$err" \
    '{status:$status,exit_code:$exit_code,report_path:$report,stdout_path:$stdout,stderr_path:$stderr,current_ga_blocker:false,role:"HISTORICAL_PROVENANCE_RECOVERY"}'
}

pre_reboot() {
  local legacy physical_rc=0 physical='{}'
  legacy="$(legacy_recovery)"
  set +e
  CENTINAL26_REPO_ROOT="$REPO_ROOT" "$PHYSICAL_GATE" --pre-reboot \
    > "$GATE_ROOT/current_physical_pre_stdout.json" \
    2> "$GATE_ROOT/current_physical_pre_stderr.log"
  physical_rc=$?
  set -e
  if [ -f "$GATE_ROOT/pre_reboot.json" ]; then
    physical="$(cat "$GATE_ROOT/pre_reboot.json")"
  fi
  jq -n \
    --arg schema "centinal26.automation_project_finalization/v1" \
    --arg phase "$( [ "$physical_rc" -eq 20 ] && echo AWAITING_REBOOT || echo PRE_REBOOT_BLOCKED )" \
    --arg observed_at "$(now_iso)" \
    --argjson physical_rc "$physical_rc" \
    --argjson legacy "$legacy" \
    --argjson physical "$physical" \
    '{schema:$schema,phase:$phase,observed_at:$observed_at,current_release:{target:"1.0.0",legacy_rc4_required:false,physical_pre_reboot:(if $physical_rc==20 then "PASS" else "BLOCKED" end)},legacy_rc4:$legacy,physical:$physical}' \
    > "$PRE_REPORT.tmp"
  mv "$PRE_REPORT.tmp" "$PRE_REPORT"
  cat "$PRE_REPORT"
  [ "$physical_rc" -eq 20 ] && exit 20
  exit "$physical_rc"
}

device_sync_probe() {
  local config="$HOME/.automation_os_github/config" issue response report_sha
  [ -f "$config" ] || { echo '{"status":"BLOCKED","reason":"missing_github_config"}'; return 1; }
  # shellcheck disable=SC1090
  source "$config"
  issue="$(cat "$GATE_ROOT/active_issue" 2>/dev/null || true)"
  [ -n "$issue" ] || { echo '{"status":"BLOCKED","reason":"missing_active_issue"}'; return 1; }
  report_sha="$(sha_file "$GATE_ROOT/endurance_report.json")"
  response="$(curl --fail-with-body -sS \
    --connect-timeout 10 --max-time 30 --retry 2 --retry-delay 2 --retry-all-errors \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${issue}/comments" \
    -d "$(jq -n --arg body "DEVICE-SYNC PASS: Android/Termux finalization endurance evidence produced. endurance_sha256=$report_sha" '{body:$body}')")" || return 1
  jq -n \
    --arg status PASS \
    --arg issue "$issue" \
    --arg comment_id "$(jq -r '.id // empty' <<<"$response")" \
    --arg comment_url "$(jq -r '.html_url // empty' <<<"$response")" \
    --arg endurance_sha256 "$report_sha" \
    '{status:$status,issue_number:$issue,comment_id:$comment_id,comment_url:$comment_url,endurance_sha256:$endurance_sha256}' \
    > "$SYNC_REPORT.tmp"
  mv "$SYNC_REPORT.tmp" "$SYNC_REPORT"
  cat "$SYNC_REPORT"
}

post_reboot() {
  if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "FINALIZATION_IN_PROGRESS"
    exit 0
  fi
  trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

  local physical_rc=0 endurance_rc=0 sync_rc=0 verify_rc=0 physical='{}' endurance='{}' sync='{}' verification='{}' legacy='{}'
  set +e
  CENTINAL26_REPO_ROOT="$REPO_ROOT" "$PHYSICAL_GATE" --post-reboot \
    > "$GATE_ROOT/current_physical_post_stdout.json" \
    2> "$GATE_ROOT/current_physical_post_stderr.log"
  physical_rc=$?
  set -e
  [ "$physical_rc" -eq 0 ] || exit "$physical_rc"
  physical="$(cat "$GATE_ROOT/post_reboot.json")"

  set +e
  CENTINAL26_ENDURANCE_SAMPLES=61 \
  CENTINAL26_ENDURANCE_INTERVAL=60 \
  CENTINAL26_ENDURANCE_MIN_SECONDS=3500 \
  CENTINAL26_REPO_ROOT="$REPO_ROOT" \
    "$ENDURANCE" > "$GATE_ROOT/endurance_stdout.json" 2> "$GATE_ROOT/endurance_stderr.log"
  endurance_rc=$?
  set -e
  [ -f "$GATE_ROOT/endurance_report.json" ] && endurance="$(cat "$GATE_ROOT/endurance_report.json")"

  if [ "$endurance_rc" -eq 0 ]; then
    set +e
    device_sync_probe > "$GATE_ROOT/device_sync_stdout.json" 2> "$GATE_ROOT/device_sync_stderr.log"
    sync_rc=$?
    set -e
    [ -f "$SYNC_REPORT" ] && sync="$(cat "$SYNC_REPORT")"
  else
    sync_rc=1
  fi

  if [ "$physical_rc" -eq 0 ] && [ "$endurance_rc" -eq 0 ] && [ "$sync_rc" -eq 0 ]; then
    set +e
    AUTOMATION_INTELLIGENCE_GATE_ROOT="$GATE_ROOT" python "$VERIFIER" > "$GATE_ROOT/independent_verification_stdout.json" 2> "$GATE_ROOT/independent_verification_stderr.log"
    verify_rc=$?
    set -e
    [ -f "$GATE_ROOT/independent_verification.json" ] && verification="$(cat "$GATE_ROOT/independent_verification.json")"
  else
    verify_rc=1
  fi

  if [ -f "$PRE_REPORT" ]; then
    legacy="$(jq -c '.legacy_rc4 // {}' "$PRE_REPORT" 2>/dev/null || echo '{}')"
  fi

  jq -n \
    --arg schema "centinal26.automation_project_finalization/v1" \
    --arg observed_at "$(now_iso)" \
    --argjson physical_rc "$physical_rc" \
    --argjson endurance_rc "$endurance_rc" \
    --argjson sync_rc "$sync_rc" \
    --argjson verify_rc "$verify_rc" \
    --argjson physical "$physical" \
    --argjson endurance "$endurance" \
    --argjson sync "$sync" \
    --argjson verification "$verification" \
    --argjson legacy "$legacy" \
    '{schema:$schema,phase:(if ($physical_rc==0 and $endurance_rc==0 and $sync_rc==0 and $verify_rc==0) then "READY_FOR_GA_PROMOTION" else "BLOCKED" end),observed_at:$observed_at,current_release:{target:"1.0.0",legacy_rc4_required:false,physical_gate:(if $physical_rc==0 then "PASS" else "FAIL" end),endurance:(if $endurance_rc==0 then "PASS" else "FAIL" end),device_sync:(if $sync_rc==0 then "PASS" else "FAIL" end),independent_verification:(if $verify_rc==0 then "PASS" else "FAIL" end),automatic_promotion_ready:($physical_rc==0 and $endurance_rc==0 and $sync_rc==0 and $verify_rc==0)},legacy_rc4:$legacy,physical:$physical,endurance:$endurance,device_sync:$sync,independent_verification:$verification}' \
    > "$FINAL_REPORT.tmp"
  mv "$FINAL_REPORT.tmp" "$FINAL_REPORT"
  cat "$FINAL_REPORT"
  [ "$(jq -r '.phase' "$FINAL_REPORT")" = "READY_FOR_GA_PROMOTION" ]
}

case "$MODE" in
  --pre-reboot) pre_reboot ;;
  --post-reboot) post_reboot ;;
  *) echo "usage: $0 [--pre-reboot|--post-reboot]" >&2; exit 64 ;;
esac
