#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config"
STATE="${HOME}/.automation_os_github/state"
[ -f "$CONFIG" ] || exit 2
# shellcheck disable=SC1090
source "$CONFIG"
num="$(cat "$STATE/active_issue" 2>/dev/null || true)"
[ -n "$num" ] || exit 0

api() {
  curl --fail-with-body -sS \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$@"
}

comment() {
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}/comments" \
    -d "$(jq -n --arg body "$1" '{body:$body}')" >/dev/null
}

labels() {
  local j
  j="$(printf '%s\n' "$@" | jq -R . | jq -s .)"
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}/labels" \
    -d "$(jq -n --argjson labels "$j" '{labels:$labels}')" >/dev/null
}

phase="$(jq -r '.phase // "UNKNOWN"' "$HOME/.automation_os_ga/state.json" 2>/dev/null || echo UNKNOWN)"
decision="$(find "$HOME/.automation_os_ga" -name PHYSICAL_EVIDENCE_DECISION.json -type f 2>/dev/null | sort | tail -n1 || true)"
final="$(find "$HOME/.automation_os_ga" -name FINAL_GA_EVALUATION.json -type f 2>/dev/null | sort | tail -n1 || true)"

if [ "$phase" = "GA_PASS" ] && [ -n "$decision" ] && grep -q '"decision": "ACCEPT"' "$decision" && [ -n "$final" ]; then
  dsha="$(sha256sum "$decision" | awk '{print $1}')"
  fsha="$(sha256sum "$final" | awk '{print $1}')"
  comment "POST-REBOOT VERIFIED: evidence_guard=ACCEPT decision_sha256=$dsha final_sha256=$fsha"
  labels automation-os-job automation-os-completed automation-os-ga-pass
  api -X PATCH "https://api.github.com/repos/${GITHUB_REPO}/issues/${num}" -d '{"state":"closed"}' >/dev/null
  exit 0
fi

comment "POST-REBOOT: phase=$phase; GA not promoted or evidence_guard not ACCEPT."
labels automation-os-job automation-os-failed
exit 8
