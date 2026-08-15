#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
GATE="$REPO_ROOT/termux/intelligence_controller_physical_gate.sh"
[ -f "$CONFIG" ] || exit 2
# shellcheck disable=SC1090
source "$CONFIG"
num="$(cat "$GATE_ROOT/active_issue" 2>/dev/null || true)"
[ -n "$num" ] || exit 0
[ -f "$GATE_ROOT/pre_reboot.json" ] || exit 0
[ -f "$GATE_ROOT/post_reboot.json" ] && exit 0

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
CENTINAL26_REPO_ROOT="$REPO_ROOT" "$GATE" --post-reboot > "$GATE_ROOT/post_reboot_stdout.json" 2> "$GATE_ROOT/post_reboot_stderr.log"
rc=$?
set -e
if [ "$rc" -eq 0 ] && [ -f "$GATE_ROOT/post_reboot.json" ]; then
  report_sha="$(sha256sum "$GATE_ROOT/post_reboot.json" | awk '{print $1}')"
  comment_issue "PHYSICAL VALIDATION PASS: reboot changed, Termux:Boot returned the controller, heartbeat is fresh, event chain is valid, and a post-reboot controller job completed. report_sha256=$report_sha"
  api -X PATCH "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}" -d '{"state":"closed","state_reason":"completed"}' >/dev/null
  exit 0
fi
comment_issue "POST-REBOOT FAIL/BLOCKED: rc=$rc. No physical promotion performed; inspect ~/.automation_intelligence_gate/."
exit "$rc"
