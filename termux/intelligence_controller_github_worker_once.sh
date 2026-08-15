#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config.json"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
FINALIZER="$REPO_ROOT/termux/automation_project_finalizer.sh"
CLAIM_MARKER="$GATE_ROOT/claimed_issue_boot"
ALLOWED_COMMAND="automation_project_finalize_v1"
RUNTIME_CONFIG="$REPO_ROOT/termux/github_runtime_config.sh"
mkdir -p "$GATE_ROOT"

if [ "${1:-}" = "--validate-command" ]; then
  candidate="${2:-}"
  if [ "$candidate" = "$ALLOWED_COMMAND" ]; then
    echo "ALLOWED_COMMAND $candidate"
    exit 0
  fi
  echo "DENIED_UNSUPPORTED_COMMAND $candidate" >&2
  exit 65
fi

[ -f "$RUNTIME_CONFIG" ] || { echo "Missing runtime config helper: $RUNTIME_CONFIG"; exit 2; }
# shellcheck disable=SC1090
source "$RUNTIME_CONFIG"
github_runtime_load_config "$CONFIG"

boot_id() {
  if [ -r /proc/sys/kernel/random/boot_id ]; then
    cat /proc/sys/kernel/random/boot_id
  else
    awk '$1 == "btime" {print "btime:" $2}' /proc/stat 2>/dev/null || echo unknown
  fi
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
  local n="$1" body="$2"
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${n}/comments" \
    -d "$(jq -n --arg body "$body" '{body:$body}')" >/dev/null
}

issue="$(api "https://api.github.com/repos/${GITHUB_REPO}/issues?state=open&per_page=100&sort=created&direction=asc" \
  | jq --arg command "$ALLOWED_COMMAND" '[.[] | select(.pull_request == null) | . as $i | ((.body // "{}") | fromjson? // {}) as $b | select($b.schema == "automation.github_job/v2" and $b.command == $command) | $i][0] // empty')"
[ -n "$issue" ] || { echo "NO_FINALIZATION_JOB"; exit 0; }

num="$(jq -r '.number' <<<"$issue")"
job="$(jq -r '(.body // "{}") | fromjson? // {}' <<<"$issue")"
command="$(jq -r '.command // empty' <<<"$job")"
"$0" --validate-command "$command" >/dev/null
expected_branch="$(jq -r '.parameters.expected_branch // "main"' <<<"$job")"
minimum_merge_commit="$(jq -r '.parameters.minimum_merge_commit // empty' <<<"$job")"
current_branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
current_commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"

if [ "$current_branch" != "$expected_branch" ]; then
  echo "BLOCKED_BRANCH expected=$expected_branch current=$current_branch" >&2
  exit 21
fi
if [ -n "$minimum_merge_commit" ]; then
  git -C "$REPO_ROOT" cat-file -e "${minimum_merge_commit}^{commit}" 2>/dev/null || {
    echo "BLOCKED_MINIMUM_COMMIT_MISSING $minimum_merge_commit" >&2
    exit 22
  }
  git -C "$REPO_ROOT" merge-base --is-ancestor "$minimum_merge_commit" HEAD || {
    echo "BLOCKED_MINIMUM_COMMIT_NOT_ANCESTOR minimum=$minimum_merge_commit current=$current_commit" >&2
    exit 23
  }
fi

active="$(cat "$GATE_ROOT/active_issue" 2>/dev/null || true)"
if [ "$active" = "$num" ] && [ -f "$GATE_ROOT/project_pre_reboot.json" ] && [ ! -f "$GATE_ROOT/project_final.json" ]; then
  phase="$(jq -r '.phase // empty' "$GATE_ROOT/project_pre_reboot.json" 2>/dev/null || true)"
  if [ "$phase" = "AWAITING_REBOOT" ]; then
    echo "AWAITING_REBOOT issue=$num"
    exit 0
  fi
fi

printf '%s\n' "$num" > "$GATE_ROOT/active_issue"
claim_key="${num}:$(boot_id)"
previous_claim="$(cat "$CLAIM_MARKER" 2>/dev/null || true)"
if [ "$previous_claim" != "$claim_key" ]; then
  comment_issue "$num" "CLAIMED by ${AUTOMATION_DEVICE_ID:-termux-device}: starting consolidated Automation v1 physical finalization at commit $current_commit. Historical RC4 recovery is attempted as provenance only; it is not a current GA blocker. Host/session execution is not accepted as device evidence."
  printf '%s\n' "$claim_key" > "$CLAIM_MARKER.tmp"
  mv "$CLAIM_MARKER.tmp" "$CLAIM_MARKER"
fi

set +e
CENTINAL26_REPO_ROOT="$REPO_ROOT" "$FINALIZER" --pre-reboot > "$GATE_ROOT/project_pre_stdout.json" 2> "$GATE_ROOT/project_pre_stderr.log"
rc=$?
set -e

if [ "$rc" -eq 20 ]; then
  report_sha="$(sha256sum "$GATE_ROOT/project_pre_reboot.json" | awk '{print $1}')"
  legacy="$(jq -r '.legacy_rc4.status // "UNKNOWN"' "$GATE_ROOT/project_pre_reboot.json")"
  comment_issue "$num" "PRE-REBOOT FINALIZATION PASS: current Android/Termux local work, lease recovery, heartbeat advancement, and event-chain checks passed. legacy_rc4=$legacy (historical/non-blocking). report_sha256=$report_sha. REBOOT REQUIRED; reboot is intentionally not triggered remotely."
  exit 0
fi

comment_issue "$num" "PRE-REBOOT FINALIZATION FAIL/BLOCKED: rc=$rc. Evidence remains under ~/.automation_intelligence_gate/. No physical or GA promotion performed."
exit "$rc"
