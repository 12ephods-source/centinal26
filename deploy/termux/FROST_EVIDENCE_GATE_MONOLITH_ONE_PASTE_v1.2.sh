#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

# Frost Evidence Gate — one-paste, reboot-resumable Termux monolith.
# Safe local steps run automatically. External credentials/configuration and the
# physical reboot remain explicit evidence boundaries. No promotion is emitted.

REPO="12ephods-source/centinal26"
INSTALLER_URL="https://raw.githubusercontent.com/${REPO}/main/deploy/termux/FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"
STATE_ROOT="${FROST_EVIDENCE_STATE_ROOT:-${HOME}/.local/share/frost-evidence-gate}"
BIN_DIR="${HOME}/bin"
LOG_DIR="${STATE_ROOT}/monolith"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="${LOG_DIR}/run-${STAMP}.log"
SUMMARY_JSON="${LOG_DIR}/summary-${STAMP}.json"
CURRENT_COMMISSION="${STATE_ROOT}/current_commissioning.json"
PRE_REBOOT="${STATE_ROOT}/pre_reboot.json"
POST_REBOOT="${STATE_ROOT}/post_reboot_receipt.json"

mkdir -p "${LOG_DIR}" "${BIN_DIR}"
chmod 700 "${STATE_ROOT}" "${LOG_DIR}" 2>/dev/null || true
exec > >(tee -a "${RUN_LOG}") 2>&1

say() { printf '\n==> %s\n' "$*"; }
pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[REVIEW] %s\n' "$*" >&2; }

if [ -z "${PREFIX:-}" ] || [[ "${PREFIX}" != *com.termux* ]]; then
  printf 'ERROR: run this inside Termux on Android.\n' >&2
  exit 2
fi

read_tty() {
  local prompt="$1" var="$2" value=""
  if [ -r /dev/tty ]; then
    printf '%s' "${prompt}" >/dev/tty
    IFS= read -r value </dev/tty || true
  fi
  printf -v "${var}" '%s' "${value}"
}

json_field() {
  python - "$1" "$2" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
try:
    value = json.loads(p.read_text(encoding="utf-8"))
    for part in sys.argv[2].split("."):
        value = value.get(part) if isinstance(value, dict) else None
    print("" if value is None else value)
except Exception:
    print("")
PY
}

optional() {
  local label="$1"; shift
  say "${label}"
  if "$@"; then
    pass "${label}"
    return 0
  fi
  warn "${label} did not complete; evidence already collected remains preserved."
  return 1
}

say "Install / refresh production evidence tooling"
TMP_INSTALLER="$(mktemp "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/frost-evidence-installer.XXXXXX")"
trap 'rm -f "${TMP_INSTALLER}"' EXIT
curl -fL --retry 3 --retry-delay 2 "${INSTALLER_URL}" -o "${TMP_INSTALLER}"
bash "${TMP_INSTALLER}"
export PATH="${BIN_DIR}:${PATH}"
command -v frost-evidence-gate >/dev/null
command -v frost-controller-evidence >/dev/null

say "Diagnostics and cryptographic prerequisites"
frost-evidence-gate doctor
frost-controller-evidence self-test
frost-evidence-gate init-age

CURRENT_BOOT_ID="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
MODE="PHASE_A"
WAITING_FOR_REBOOT=false
POST_REBOOT_LOCAL_OK=false

# Resume before any fresh commissioning. This preserves the original pre-reboot
# baseline and prevents a second paste from erasing the boot-identity comparison.
if [ -s "${PRE_REBOOT}" ]; then
  PRE_BOOT_ID="$(json_field "${PRE_REBOOT}" boot_id)"
  if [ -n "${PRE_BOOT_ID}" ] && [ -n "${CURRENT_BOOT_ID}" ] && [ "${PRE_BOOT_ID}" != "${CURRENT_BOOT_ID}" ]; then
    MODE="PHASE_B"
    say "Detected changed boot identity; resume post-reboot evidence first"
    POST_BOOT_RECORDED="$(json_field "${POST_REBOOT}" post_boot_id)"
    if [ ! -s "${POST_REBOOT}" ] || [ "${POST_BOOT_RECORDED}" != "${CURRENT_BOOT_ID}" ]; then
      if frost-evidence-gate post-reboot; then
        POST_REBOOT_LOCAL_OK=true
      else
        warn "Post-reboot capture is incomplete; preserving Phase B as pending."
      fi
    else
      POST_REBOOT_LOCAL_OK=true
      pass "Existing post-reboot receipt matches the current boot session"
    fi
  elif [ -n "${PRE_BOOT_ID}" ] && [ "${PRE_BOOT_ID}" = "${CURRENT_BOOT_ID}" ]; then
    WAITING_FOR_REBOOT=true
    pass "Reboot transaction is already armed; original pre-reboot boot ID preserved"
  fi
fi

if [ "${MODE}" = "PHASE_A" ] && [ "${WAITING_FOR_REBOOT}" = false ]; then
  if [ "${FROST_REUSE_COMMISSIONING:-0}" = "1" ] && [ -s "${CURRENT_COMMISSION}" ]; then
    pass "Reusing commissioning by explicit FROST_REUSE_COMMISSIONING=1"
  else
    say "Capture fresh physical Android/Termux commissioning evidence"
    frost-evidence-gate commission
  fi
fi

if [ ! -s "${CURRENT_COMMISSION}" ]; then
  printf 'ERROR: commissioning receipt is unavailable.\n' >&2
  exit 2
fi

COMMISSION_ZIP="$(json_field "${CURRENT_COMMISSION}" package_path)"
DEVICE_ID="$(json_field "${CURRENT_COMMISSION}" device_id)"
BOOT_ID="$(json_field "${CURRENT_COMMISSION}" boot_id)"
ENROLLMENT_DIGEST="$(json_field "${CURRENT_COMMISSION}" enrollment_digest)"
if [ -z "${COMMISSION_ZIP}" ] || [ ! -f "${COMMISSION_ZIP}" ]; then
  printf 'ERROR: commissioning ZIP referenced by the receipt is unavailable.\n' >&2
  exit 2
fi
pass "Commissioning package: ${COMMISSION_ZIP}"

# Off-device recovery: one configured rclone remote can be selected safely;
# multiple remotes require an explicit selection. Never configure/delete remotes.
OFFDEVICE_OK=false
if [ "$(json_field "${STATE_ROOT}/offdevice_roundtrip_receipt.json" recovery_verified)" = "True" ] || \
   [ "$(json_field "${STATE_ROOT}/offdevice_roundtrip_receipt.json" recovery_verified)" = "true" ]; then
  OFFDEVICE_OK=true
  pass "Existing encrypted off-device recovery receipt is verified"
elif command -v rclone >/dev/null 2>&1; then
  REMOTE_TARGET="${FROST_RCLONE_REMOTE:-}"
  if [ -z "${REMOTE_TARGET}" ]; then
    mapfile -t REMOTES < <(rclone listremotes 2>/dev/null | sed '/^[[:space:]]*$/d' || true)
    if [ "${#REMOTES[@]}" -eq 1 ]; then
      REMOTE_TARGET="${REMOTES[0]}FrostEvidence/${DEVICE_ID}/${STAMP}"
      pass "Using the single configured rclone remote: ${REMOTES[0]}"
    elif [ "${#REMOTES[@]}" -gt 1 ]; then
      printf 'Configured rclone remotes:\n'; printf '  %s\n' "${REMOTES[@]}"
      read_tty "Remote destination (remote:path), or blank to defer: " REMOTE_TARGET
    else
      warn "No rclone remote configured; encrypted off-device round trip is pending."
    fi
  fi
  if [ -n "${REMOTE_TARGET}" ]; then
    if optional "Encrypted off-device upload/retrieval/decrypt/hash round trip" \
      frost-evidence-gate offdevice-roundtrip \
        --source "${COMMISSION_ZIP}" \
        --identity "${STATE_ROOT}/keys/age-identity.txt" \
        --remote "${REMOTE_TARGET}"; then
      OFFDEVICE_OK=true
    fi
  fi
fi

# Recover worker config from the armed transaction first, then environment and
# conservative standard locations. This makes the second paste reboot-resumable.
WORKER_CONFIG="$(json_field "${PRE_REBOOT}" worker_config_path)"
[ -n "${FROST_WORKER_CONFIG:-}" ] && WORKER_CONFIG="${FROST_WORKER_CONFIG}"
if [ -z "${WORKER_CONFIG}" ]; then
  for candidate in "${STATE_ROOT}/worker.json" "${HOME}/.config/frost/worker.json" "${HOME}/worker.json"; do
    if [ -f "${candidate}" ]; then WORKER_CONFIG="${candidate}"; break; fi
  done
fi
if [ -z "${WORKER_CONFIG}" ] && [ "${WAITING_FOR_REBOOT}" = false ]; then
  read_tty "Worker config path, or blank to defer worker/reboot gates: " WORKER_CONFIG
fi
WORKER_CONFIG="${WORKER_CONFIG/#\~/${HOME}}"

WORKER_OK=false
if [ "${MODE}" = "PHASE_B" ]; then
  POST_WORK="$(json_field "${POST_REBOOT}" post_reboot_bounded_work.bounded_work_observed)"
  if [ "${POST_WORK}" = "True" ] || [ "${POST_WORK}" = "true" ]; then
    WORKER_OK=true
    pass "Post-reboot bounded worker evidence is already observed"
  elif [ -n "${WORKER_CONFIG}" ] && [ -f "${WORKER_CONFIG}" ]; then
    optional "Retry one allowlisted post-reboot worker job" frost-evidence-gate worker-once --config "${WORKER_CONFIG}" && WORKER_OK=true || true
  fi
elif [ "${WAITING_FOR_REBOOT}" = false ] && [ -n "${WORKER_CONFIG}" ] && [ -f "${WORKER_CONFIG}" ]; then
  optional "Execute one allowlisted bounded worker job" frost-evidence-gate worker-once --config "${WORKER_CONFIG}" && WORKER_OK=true || true
elif [ "${WAITING_FOR_REBOOT}" = false ]; then
  warn "No worker config selected; bounded-work and reboot gates remain pending."
fi

# Read-only controller evidence. The physical device ID is a useful default,
# but the user may replace it if the Base44 AutomationWorker.instance_id differs.
CONTROLLER_WORKER="${FROST_CONTROLLER_WORKER_INSTANCE:-${DEVICE_ID}}"
CONTROLLER_JOB="${FROST_CONTROLLER_JOB_ID:-}"
CONTROLLER_CONTRACT="${FROST_CONTROLLER_CONTRACT_ID:-}"
CONTROLLER_PROPOSAL="${FROST_CONTROLLER_PROPOSAL_KEY:-}"
if [ "${FROST_SKIP_CONTROLLER_PROMPTS:-0}" != "1" ]; then
  input=""
  read_tty "Controller worker instance [${CONTROLLER_WORKER}] (blank keeps default): " input
  [ -n "${input}" ] && CONTROLLER_WORKER="${input}"
  read_tty "Controller job ID (blank selects newest worker-bound job): " input
  [ -n "${input}" ] && CONTROLLER_JOB="${input}"
  read_tty "Physical-release contract ID (blank defers Judge eligibility): " input
  [ -n "${input}" ] && CONTROLLER_CONTRACT="${input}"
  read_tty "Physical proposal key (optional): " input
  [ -n "${input}" ] && CONTROLLER_PROPOSAL="${input}"
fi

VERIFY_PHASE="phase-a"
[ "${MODE}" = "PHASE_B" ] && VERIFY_PHASE="phase-b"
CONTROLLER_BUNDLE="${LOG_DIR}/controller-${VERIFY_PHASE}-${STAMP}.json"
CONTROLLER_VERIFY="${LOG_DIR}/controller-${VERIFY_PHASE}-verification-${STAMP}.json"
CONTROLLER_OK=false

if [ -n "${CONTROLLER_WORKER}" ]; then
  args=(export --worker-instance "${CONTROLLER_WORKER}")
  [ -n "${CONTROLLER_JOB}" ] && args+=(--job-id "${CONTROLLER_JOB}")
  [ -n "${CONTROLLER_CONTRACT}" ] && args+=(--contract-id "${CONTROLLER_CONTRACT}")
  [ -n "${CONTROLLER_PROPOSAL}" ] && args+=(--proposal-key "${CONTROLLER_PROPOSAL}")
  say "Collect read-only controller evidence (${VERIFY_PHASE})"
  if frost-controller-evidence "${args[@]}" >"${CONTROLLER_BUNDLE}"; then
    if frost-controller-evidence verify "${CONTROLLER_BUNDLE}" --phase "${VERIFY_PHASE}" >"${CONTROLLER_VERIFY}"; then
      cat "${CONTROLLER_VERIFY}"
      CONTROLLER_OK=true
    else
      warn "Controller bundle integrity is preserved, but ${VERIFY_PHASE} eligibility is incomplete."
    fi
  else
    rm -f "${CONTROLLER_BUNDLE}"
    warn "Controller export deferred/failed; no local evidence was discarded."
  fi
fi

REBOOT_ARMED=false
if [ "${MODE}" = "PHASE_A" ] && [ "${WAITING_FOR_REBOOT}" = false ] && \
   [ -n "${WORKER_CONFIG}" ] && [ -f "${WORKER_CONFIG}" ]; then
  if optional "Arm Termux:Boot physical-reboot continuation" \
      frost-evidence-gate arm-reboot --worker-config "${WORKER_CONFIG}"; then
    REBOOT_ARMED=true
  fi
elif [ "${WAITING_FOR_REBOOT}" = true ]; then
  REBOOT_ARMED=true
fi

say "Current local evidence-gate status"
frost-evidence-gate status || true

NEXT_ACTION="COMPLETE_PENDING_EXTERNAL_CONFIGURATION"
if [ "${MODE}" = "PHASE_B" ]; then
  NEXT_ACTION="REVIEW_PHASE_B_CONTROLLER_EVIDENCE"
elif [ "${REBOOT_ARMED}" = true ]; then
  NEXT_ACTION="PHYSICAL_ANDROID_REBOOT"
fi

python - "${SUMMARY_JSON}" "${MODE}" "${NEXT_ACTION}" "${DEVICE_ID}" "${BOOT_ID}" \
  "${ENROLLMENT_DIGEST}" "${COMMISSION_ZIP}" "${OFFDEVICE_OK}" "${WORKER_OK}" \
  "${CONTROLLER_OK}" "${REBOOT_ARMED}" "${POST_REBOOT_LOCAL_OK}" \
  "${CONTROLLER_BUNDLE}" "${CONTROLLER_VERIFY}" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
(out, mode, next_action, device_id, boot_id, enrollment_digest, commissioning_zip,
 offdevice, worker, controller, reboot_armed, post_local, controller_bundle,
 controller_verify) = sys.argv[1:]
def yes(v): return v.lower() == "true"
def digest(path):
    p=Path(path)
    if not p.is_file(): return None
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024), b""): h.update(c)
    return h.hexdigest()
summary={
 "schema":"frost.evidence_gate.monolith_summary.v1.2",
 "captured_at":datetime.now(timezone.utc).isoformat(),
 "mode":mode,
 "device_id":device_id,
 "commissioning_boot_id":boot_id,
 "enrollment_digest":enrollment_digest,
 "commissioning_zip":commissioning_zip,
 "commissioning_zip_sha256":digest(commissioning_zip),
 "offdevice_roundtrip_observed":yes(offdevice),
 "bounded_worker_pass_observed":yes(worker),
 "controller_evidence_verified_or_collected":yes(controller),
 "physical_reboot_continuation_armed":yes(reboot_armed),
 "post_reboot_local_evidence_observed":yes(post_local),
 "controller_bundle":controller_bundle if Path(controller_bundle).is_file() else None,
 "controller_bundle_sha256":digest(controller_bundle),
 "controller_verification":controller_verify if Path(controller_verify).is_file() else None,
 "promotion_performed":False,
 "next_action":next_action,
}
Path(out).write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps(summary,indent=2,sort_keys=True))
PY

say "Monolith run complete"
printf 'Run log: %s\nSummary: %s\nCommissioning ZIP: %s\n' "${RUN_LOG}" "${SUMMARY_JSON}" "${COMMISSION_ZIP}"

if [ "${NEXT_ACTION}" = "PHYSICAL_ANDROID_REBOOT" ]; then
  cat <<'EOF'

NEXT REQUIRED PHYSICAL ACTION
-----------------------------
Physically reboot the Android phone from the normal device UI.
Do NOT use adb reboot, remote shell reboot, su -c reboot, or simulation.
After Android and Termux return, paste the SAME one-paste command again.
The second run will detect the changed boot ID and execute post-reboot capture
before any new commissioning, preserving the original evidence boundary.
EOF
elif [ "${MODE}" = "PHASE_B" ]; then
  cat <<'EOF'

PHASE B LOCAL RESUME COMPLETE
-----------------------------
Post-reboot local evidence was processed before any new commissioning. Review
the controller Phase B verification above. This monolith never promotes a gate;
DEVICE/PERSISTENT promotion remains an independent controller/Judge decision.
EOF
else
  cat <<'EOF'

PENDING EXTERNAL INPUTS
-----------------------
The physical commissioning package is preserved. Configure/provide any missing
worker, Base44/controller, or rclone inputs reported above, then paste the same
one-paste command again. Missing evidence never becomes evidence of absence.
EOF
fi
