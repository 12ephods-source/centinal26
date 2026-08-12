#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CONFIG="${HOME}/.automation_os_github/config"
STATE="${HOME}/.automation_os_github/state"
PATCHED_ARTIFACT_NAME="AUTOMATION_OS_1.0.0_RC9_VALIDATION_INTEGRITY_PATCH.zip"
PATCHED_ARTIFACT_SHA256="8568085fcc44d46a31512ca58c3af863392fcc09cd65fa0e38e46754e0a6b018"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDITOR="$REPO_ROOT/scripts/audit_untrusted_candidate.py"
REVIEW_REGISTRY="$REPO_ROOT/security/reviewed_artifacts.json"

mkdir -p "$(dirname "$CONFIG")" "$STATE"
[ -f "$CONFIG" ] || { echo "Missing $CONFIG"; exit 2; }
[ -f "$AUDITOR" ] || { echo "Missing adversarial audit gate: $AUDITOR"; exit 2; }
[ -f "$REVIEW_REGISTRY" ] || { echo "Missing reviewed-artifact registry: $REVIEW_REGISTRY"; exit 2; }
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

set_labels() {
  local n="$1"; shift
  local j
  j="$(printf '%s\n' "$@" | jq -R . | jq -s .)"
  api -X POST "https://api.github.com/repos/${GITHUB_REPO}/issues/${n}/labels" \
    -d "$(jq -n --argjson labels "$j" '{labels:$labels}')" >/dev/null
}

reviewed_findings_allow() {
  local artifact_sha="$1" findings_sha="$2"
  jq -e \
    --arg artifact_sha "$artifact_sha" \
    --arg findings_sha "$findings_sha" \
    '.schema == "centinal26-reviewed-artifacts-v1" and
     any(.artifacts[]?;
       .sha256 == $artifact_sha and
       .findings_sha256 == $findings_sha and
       .status == "REVIEWED_ALLOW" and
       (.reviewer | type == "string" and length > 0) and
       (.reviewed_at | type == "string" and length > 0) and
       (.rationale | type == "string" and length > 0))' \
    "$REVIEW_REGISTRY" >/dev/null
}

issue="$(api "https://api.github.com/repos/${GITHUB_REPO}/issues?labels=automation-os-job&state=open&per_page=20" \
  | jq '[.[] | select(([.labels[].name] | index("automation-os-claimed")) | not)][0] // empty')"
[ -n "$issue" ] || { echo "NO_JOB"; exit 0; }

num="$(jq -r '.number' <<<"$issue")"
body="$(jq -r '.body' <<<"$issue")"
schema="$(jq -r '.schema // empty' <<<"$body")"
command_name="$(jq -r '.command // empty' <<<"$body")"
iterations="$(jq -r '.parameters.endurance_iterations // 100' <<<"$body")"

if [ "$schema" != "automation.github_job/v2" ] || [ "$command_name" != "automation_os_physical_ga_rc9_integrity" ]; then
  comment_issue "$num" "REJECTED: unsupported schema/command."
  set_labels "$num" automation-os-job automation-os-rejected
  exit 3
fi

set_labels "$num" automation-os-job automation-os-claimed
comment_issue "$num" "CLAIMED by ${AUTOMATION_DEVICE_ID:-termux-device}. Pin verification and behavior review are independent gates; names such as test/qualification/PIN do not authorize execution."

ART="${AUTOMATION_OS_PATCHED_RC9_PATH:-$HOME/storage/downloads/$PATCHED_ARTIFACT_NAME}"
if [ ! -f "$ART" ] && [ -n "${AUTOMATION_OS_PATCHED_RC9_URL:-}" ]; then
  mkdir -p "$(dirname "$ART")"
  curl --fail-with-body -L "$AUTOMATION_OS_PATCHED_RC9_URL" -o "$ART"
fi
if [ ! -f "$ART" ]; then
  comment_issue "$num" "BLOCKED: patched RC9 artifact not found at $ART. Expected SHA-256 $PATCHED_ARTIFACT_SHA256."
  set_labels "$num" automation-os-job automation-os-failed
  exit 4
fi

actual="$(sha256sum "$ART" | awk '{print $1}')"
if [ "$actual" != "$PATCHED_ARTIFACT_SHA256" ]; then
  comment_issue "$num" "FAIL: patched RC9 hash mismatch. expected=$PATCHED_ARTIFACT_SHA256 actual=$actual"
  set_labels "$num" automation-os-job automation-os-failed
  exit 5
fi

# The pin authenticates expected bytes only. It does not establish benign behavior.
audit_report="$STATE/artifact-audit-${num}-${actual:0:12}.json"
set +e
python "$AUDITOR" "$ART" \
  --expected-sha256 "$PATCHED_ARTIFACT_SHA256" \
  --output "$audit_report" >/dev/null
audit_rc=$?
set -e

audit_reason="$(jq -r '.reason // "UNKNOWN"' "$audit_report" 2>/dev/null || echo UNKNOWN)"
findings_sha="$(jq -cS '.findings // []' "$audit_report" 2>/dev/null | sha256sum | awk '{print $1}')"

if [ "$audit_rc" -ne 0 ]; then
  critical_count="$(jq '[.findings[]? | select(.severity == "critical")] | length' "$audit_report" 2>/dev/null || echo '?')"
  high_count="$(jq '[.findings[]? | select(.severity == "high")] | length' "$audit_report" 2>/dev/null || echo '?')"
  if [ "$audit_reason" = "BEHAVIOR_REVIEW_REQUIRED" ] && reviewed_findings_allow "$actual" "$findings_sha"; then
    comment_issue "$num" "SECURITY REVIEW MATCH: artifact=$actual findings=$findings_sha. Version-controlled REVIEWED_ALLOW entry matches this exact behavior fingerprint; proceeding to bounded execution."
  else
    comment_issue "$num" "SECURITY BLOCK: pinned artifact failed independent behavior gate. reason=$audit_reason critical=$critical_count high=$high_count artifact=$actual findings=$findings_sha. No artifact code was executed."
    set_labels "$num" automation-os-job automation-os-rejected automation-os-security-review
    exit 23
  fi
fi

cp "$audit_report" "$STATE/last-approved-artifact-audit.json"
printf '%s\n' "$findings_sha" > "$STATE/last-approved-findings.sha256"
echo "$num" > "$STATE/active_issue"

WORK="$HOME/automation-os-github-control"
rm -rf "$WORK/deploy"
mkdir -p "$WORK/deploy"
unzip -q "$ART" -d "$WORK/deploy"
bundle="$(find "$WORK/deploy" -maxdepth 1 -mindepth 1 -type d | head -n1)"
[ -n "$bundle" ] || { comment_issue "$num" "FAIL: extraction failed"; exit 6; }

export AUTOMATION_OS_ENDURANCE_ITERATIONS="$iterations"
set +e
bash "$bundle/AUTOMATE_TO_GA_RC9.sh"
rc=$?
set -e
phase="$(jq -r '.phase // "UNKNOWN"' "$HOME/.automation_os_ga/state.json" 2>/dev/null || echo UNKNOWN)"
comment_issue "$num" "Patched RC9 pre-reboot rc=$rc phase=$phase."

if [ "$phase" = "AWAITING_REBOOT" ]; then
  set_labels "$num" automation-os-job automation-os-claimed automation-os-awaiting-reboot
  comment_issue "$num" "REBOOT REQUIRED: after boot, integrity guard must ACCEPT PHYSICAL_EVIDENCE_REPORT before GA promotion."
  exit 0
fi

set_labels "$num" automation-os-job automation-os-failed
comment_issue "$num" "FAIL/BLOCKED before reboot; evidence preserved on device."
exit 7
