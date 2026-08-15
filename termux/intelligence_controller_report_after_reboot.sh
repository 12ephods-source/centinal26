#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config.json"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
FINALIZER="$REPO_ROOT/termux/automation_project_finalizer.sh"
RUNTIME_CONFIG="$REPO_ROOT/termux/github_runtime_config.sh"
[ -f "$RUNTIME_CONFIG" ] || exit 2
# shellcheck disable=SC1090
source "$RUNTIME_CONFIG"
github_runtime_load_config "$CONFIG"
num="$(cat "$GATE_ROOT/active_issue" 2>/dev/null || true)"
[ -n "$num" ] || exit 0
[ -f "$GATE_ROOT/project_pre_reboot.json" ] || exit 0
[ -f "$GATE_ROOT/project_final.json" ] && {
  [ "$(jq -r '.phase // empty' "$GATE_ROOT/project_final.json")" = "READY_FOR_GA_PROMOTION" ] && exit 0
}

api() {
  curl --fail-with-body -sS \
    --connect-timeout 10 \
    --max-time 30 \
    --retry 2 \
    --retry-delay 2 \
    --retry-all-errors \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$@"
}
comment_issue() {
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}/comments" \
    -d "$(jq -n --arg body "$1" '{body:$body}')" >/dev/null
}

set +e
CENTINAL26_REPO_ROOT="$REPO_ROOT" "$FINALIZER" --post-reboot > "$GATE_ROOT/project_post_stdout.json" 2> "$GATE_ROOT/project_post_stderr.log"
rc=$?
set -e
if [ "$rc" -eq 0 ] && [ -f "$GATE_ROOT/project_final.json" ] && [ "$(jq -r '.phase // empty' "$GATE_ROOT/project_final.json")" = "READY_FOR_GA_PROMOTION" ]; then
  report_sha="$(sha256sum "$GATE_ROOT/project_final.json" | awk '{print $1}')"
  endurance_sha="$(sha256sum "$GATE_ROOT/endurance_report.json" | awk '{print $1}')"
  comment_issue "PHYSICAL FINALIZATION PASS: real reboot/Termux:Boot return, controller continuity, post-reboot work, 61-sample >=3500-second endurance, fail-closed unsupported-command rejection, watchdog recovery drill, event-chain validity, device-sync evidence, and independent verification passed. project_final_sha256=$report_sha endurance_sha256=$endurance_sha. Current release is READY_FOR_GA_PROMOTION; historical RC4 recovery is not a modern GA blocker."
  api -X PATCH "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}" -d '{"state":"closed","state_reason":"completed"}' >/dev/null
  exit 0
fi
comment_issue "POST-REBOOT FINALIZATION FAIL/BLOCKED: rc=$rc. No GA promotion performed; inspect ~/.automation_intelligence_gate/."
exit "$rc"
