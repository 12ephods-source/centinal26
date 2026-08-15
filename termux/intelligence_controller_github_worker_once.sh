#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
GATE="$REPO_ROOT/termux/intelligence_controller_physical_gate.sh"
mkdir -p "$GATE_ROOT"
[ -f "$CONFIG" ] || { echo "Missing $CONFIG"; exit 2; }
# shellcheck disable=SC1090
source "$CONFIG"

api() {
  curl --fail-with-body -sS \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$@"
}

comment_issue() {
  local n="$1" body="$2"
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${n}/comments" \
    -d "$(jq -n --arg body "$body" '{body:$body}')" >/dev/null
}

issue="$(api "https://api.github.com/repos/${GITHUB_REPO}/issues?state=open&per_page=100&sort=created&direction=asc" \
  | jq '[.[] | select(.pull_request == null) | . as $i | ((.body // "{}") | fromjson? // {}) as $b | select($b.schema == "automation.github_job/v2" and $b.command == "intelligence_controller_physical_gate_v1") | $i][0] // empty')"
[ -n "$issue" ] || { echo "NO_INTELLIGENCE_JOB"; exit 0; }

num="$(jq -r '.number' <<<"$issue")"
active="$(cat "$GATE_ROOT/active_issue" 2>/dev/null || true)"
if [ "$active" = "$num" ] && [ -f "$GATE_ROOT/pre_reboot.json" ] && [ ! -f "$GATE_ROOT/post_reboot.json" ]; then
  echo "AWAITING_REBOOT issue=$num"
  exit 0
fi

printf '%s\n' "$num" > "$GATE_ROOT/active_issue"
comment_issue "$num" "CLAIMED by ${AUTOMATION_DEVICE_ID:-termux-device}: starting Automation Intelligence Controller physical pre-reboot gate. Host/session execution is not accepted as device evidence."

set +e
CENTINAL26_REPO_ROOT="$REPO_ROOT" "$GATE" --pre-reboot > "$GATE_ROOT/pre_reboot_stdout.json" 2> "$GATE_ROOT/pre_reboot_stderr.log"
rc=$?
set -e

if [ "$rc" -eq 20 ]; then
  report_sha="$(sha256sum "$GATE_ROOT/pre_reboot.json" | awk '{print $1}')"
  comment_issue "$num" "PRE-REBOOT PASS: physical Android/Termux job execution, lease recovery, heartbeat advancement, and event-chain checks passed. report_sha256=$report_sha. REBOOT REQUIRED to prove Termux:Boot return; reboot is intentionally not triggered remotely."
  exit 0
fi

comment_issue "$num" "PRE-REBOOT FAIL/BLOCKED: rc=$rc. Evidence remains under ~/.automation_intelligence_gate/. No physical promotion performed."
exit "$rc"
