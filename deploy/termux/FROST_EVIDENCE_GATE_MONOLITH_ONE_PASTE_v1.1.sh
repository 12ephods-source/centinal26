#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

# Frost Evidence Gate — one-paste orchestration monolith.
# It performs every safe/local step automatically and leaves only genuinely
# external facts (credentials, configured remote, physical reboot) as gates.

REPO="12ephods-source/centinal26"
INSTALLER_URL="https://raw.githubusercontent.com/${REPO}/main/deploy/termux/FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"
STATE_ROOT="${FROST_EVIDENCE_STATE_ROOT:-${HOME}/.local/share/frost-evidence-gate}"
BIN_DIR="${HOME}/bin"
LOG_DIR="${STATE_ROOT}/monolith"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="${LOG_DIR}/run-${STAMP}.log"
SUMMARY_JSON="${LOG_DIR}/summary-${STAMP}.json"

mkdir -p "${LOG_DIR}" "${BIN_DIR}"
chmod 700 "${STATE_ROOT}" "${LOG_DIR}" 2>/dev/null || true
exec > >(tee -a "${RUN_LOG}") 2>&1

say() { printf '\n==> %s\n' "$*"; }
warn() { printf '\n[REVIEW] %s\n' "$*" >&2; }
pass() { printf '[PASS] %s\n' "$*"; }

if [ -z "${PREFIX:-}" ] || [[ "${PREFIX}" != *com.termux* ]]; then
  printf 'ERROR: run this inside Termux on Android.\n' >&2
  exit 2
fi

# Keep the monolith resilient: an optional external step may fail without
# erasing evidence already collected. Required local setup/commissioning fails
# closed and terminates.
step_optional() {
  local label="$1"; shift
  say "${label}"
  if "$@"; then
    pass "${label}"
    return 0
  fi
  warn "${label} did not complete; preserved as pending."
  return 1
}

read_tty() {
  local prompt="$1"
  local __var="$2"
  local value=""
  if [ -r /dev/tty ]; then
    printf '%s' "${prompt}" >/dev/tty
    IFS= read -r value </dev/tty || true
  fi
  printf -v "${__var}" '%s' "${value}"
}

json_field() {
  local file="$1" field="$2"
  python - "$file" "$field" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
field = sys.argv[2]
try:
    obj = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
value = obj
for part in field.split("."):
    if not isinstance(value, dict):
        value = None
        break
    value = value.get(part)
print("" if value is None else value)
PY
}

say "Install / refresh qualified evidence tooling"
TMP_INSTALLER="$(mktemp "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/frost-evidence-installer.XXXXXX")"
trap 'rm -f "${TMP_INSTALLER}"' EXIT
curl -fL --retry 3 --retry-delay 2 "${INSTALLER_URL}" -o "${TMP_INSTALLER}"
bash "${TMP_INSTALLER}"
export PATH="${BIN_DIR}:${PATH}"
command -v frost-evidence-gate >/dev/null
command -v frost-controller-evidence >/dev/null

say "Local diagnostics"
frost-evidence-gate doctor
frost-controller-evidence self-test

say "Initialize local age recovery identity"
frost-evidence-gate init-age

CURRENT_COMMISSION="${STATE_ROOT}/current_commissioning.json"
if [ "${FROST_REUSE_COMMISSIONING:-0}" = "1" ] && [ -s "${CURRENT_COMMISSION}" ]; then
  pass "Reusing existing commissioning receipt by explicit FROST_REUSE_COMMISSIONING=1"
else
  say "Capture fresh physical Android/Termux commissioning evidence"
  frost-evidence-gate commission
fi

if [ ! -s "${CURRENT_COMMISSION}" ]; then
  printf 'ERROR: commissioning receipt was not created.\n' >&2
  exit 2
fi

COMMISSION_ZIP="$(json_field "${CURRENT_COMMISSION}" package_path)"
DEVICE_ID="$(json_field "${CURRENT_COMMISSION}" device_id)"
BOOT_ID="$(json_field "${CURRENT_COMMISSION}" boot_id)"
ENROLLMENT_DIGEST="$(json_field "${CURRENT_COMMISSION}" enrollment_digest)"
if [ -z "${COMMISSION_ZIP}" ] || [ ! -f "${COMMISSION_ZIP}" ]; then
  printf 'ERROR: commissioning ZIP is missing from receipt.\n' >&2
  exit 2
fi
pass "Commissioning package: ${COMMISSION_ZIP}"

# Resolve an off-device destination. Exactly one configured rclone remote is
# safe to use automatically; otherwise require an explicit user-selected path.
REMOTE_TARGET="${FROST_RCLONE_REMOTE:-}"
if command -v rclone >/dev/null 2>&1 && [ -z "${REMOTE_TARGET}" ]; then
  mapfile -t REMOTES < <(rclone listremotes 2>/dev/null | sed '/^[[:space:]]*$/d' || true)
  if [ "${#REMOTES[@]}" -eq 1 ]; then
    REMOTE_TARGET="${REMOTES[0]}FrostEvidence/${DEVICE_ID}/${STAMP}"
    pass "Using the single configured rclone remote: ${REMOTES[0]}"
  elif [ "${#REMOTES[@]}" -gt 1 ]; then
    printf '\nConfigured rclone remotes:\n'
    printf '  %s\n' "${REMOTES[@]}"
    read_tty "Remote destination (for example remote:FrostEvidence/device), or blank to defer: " REMOTE_TARGET
  else
    warn "No rclone remote is configured. Off-device recovery will remain pending."
  fi
fi

OFFDEVICE_OK=false
if [ -n "${REMOTE_TARGET}" ]; then
  if step_optional "Encrypted off-device upload/retrieval/decrypt/hash round trip" \
    frost-evidence-gate offdevice-roundtrip \
      --source "${COMMISSION_ZIP}" \
      --identity "${STATE_ROOT}/keys/age-identity.txt" \
      --remote "${REMOTE_TARGET}"; then
    OFFDEVICE_OK=true
  fi
fi

# Worker configuration can be supplied non-interactively or selected once.
WORKER_CONFIG="${FROST_WORKER_CONFIG:-}"
if [ -z "${WORKER_CONFIG}" ]; then
  for candidate in \
    "${STATE_ROOT}/worker.json" \
    "${HOME}/.config/frost/worker.json" \
    "${HOME}/worker.json"; do
    if [ -f "${candidate}" ]; then
      WORKER_CONFIG="${candidate}"
      pass "Detected worker config: ${WORKER_CONFIG}"
      break
    fi
  done
fi
if [ -z "${WORKER_CONFIG}" ]; then
  read_tty "Worker config path, or blank to defer bounded-work/reboot gates: " WORKER_CONFIG
fi
if [ -n "${WORKER_CONFIG}" ]; then
  WORKER_CONFIG="${WORKER_CONFIG/#\~/${HOME}}"
fi

WORKER_OK=false
REBOOT_ARMED=false
if [ -n "${WORKER_CONFIG}" ] && [ -f "${WORKER_CONFIG}" ]; then
  if step_optional "Execute one allowlisted bounded worker job" \
    frost-evidence-gate worker-once --config "${WORKER_CONFIG}"; then
    WORKER_OK=true
  fi
else
  warn "No valid worker config selected; bounded worker evidence is pending."
fi

# Controller-side evidence. We can default the worker selector to the physical
# device ID, but the operator may replace it if the Base44 instance_id differs.
CONTROLLER_WORKER="${FROST_CONTROLLER_WORKER_INSTANCE:-${DEVICE_ID}}"
CONTROLLER_JOB="${FROST_CONTROLLER_JOB_ID:-}"
CONTROLLER_CONTRACT="${FROST_CONTROLLER_CONTRACT_ID:-}"
CONTROLLER_PROPOSAL="${FROST_CONTROLLER_PROPOSAL_KEY:-}"

if [ "${FROST_SKIP_CONTROLLER_PROMPTS:-0}" != "1" ]; then
  local_input=""
  read_tty "Controller worker instance [${CONTROLLER_WORKER}] (blank keeps default): " local_input
  [ -n "${local_input}" ] && CONTROLLER_WORKER="${local_input}"
  read_tty "Controller job ID (blank lets exporter select newest worker-bound job): " local_input
  [ -n "${local_input}" ] && CONTROLLER_JOB="${local_input}"
  read_tty "Physical-release contract ID (blank defers independent-Judge eligibility): " local_input
  [ -n "${local_input}" ] && CONTROLLER_CONTRACT="${local_input}"
  read_tty "Physical proposal key (optional; useful for Phase B): " local_input
  [ -n "${local_input}" ] && CONTROLLER_PROPOSAL="${local_input}"
fi

CONTROLLER_BUNDLE="${LOG_DIR}/controller-phase-a-${STAMP}.json"
CONTROLLER_VERIFY="${LOG_DIR}/controller-phase-a-verification-${STAMP}.json"
CONTROLLER_OK=false

if [ -n "${CONTROLLER_WORKER}" ]; then
  export_args=(export --worker-instance "${CONTROLLER_WORKER}")
  [ -n "${CONTROLLER_JOB}" ] && export_args+=(--job-id "${CONTROLLER_JOB}")
  [ -n "${CONTROLLER_CONTRACT}" ] && export_args+=(--contract-id "${CONTROLLER_CONTRACT}")
  [ -n "${CONTROLLER_PROPOSAL}" ] && export_args+=(--proposal-key "${CONTROLLER_PROPOSAL}")

  say "Collect read-only controller evidence"
  if frost-controller-evidence "${export_args[@]}" >"${CONTROLLER_BUNDLE}"; then
    if frost-controller-evidence verify "${CONTROLLER_BUNDLE}" --phase phase-a >"${CONTROLLER_VERIFY}"; then
      CONTROLLER_OK=true
      pass "Controller bundle collected and integrity-verified"
      cat "${CONTROLLER_VERIFY}"
    else
      warn "Controller bundle was collected but Phase A eligibility verification is not complete."
    fi
  else
    rm -f "${CONTROLLER_BUNDLE}"
    warn "Controller export deferred/failed; local evidence remains preserved."
  fi
fi

# Arm physical reboot only after a valid worker config exists. This does NOT
# reboot the phone; remote reboot is intentionally excluded.
if [ -n "${WORKER_CONFIG}" ] && [ -f "${WORKER_CONFIG}" ]; then
  if step_optional "Arm Termux:Boot post-reboot evidence continuation" \
    frost-evidence-gate arm-reboot --worker-config "${WORKER_CONFIG}"; then
    REBOOT_ARMED=true
  fi
fi

say "Current evidence-gate status"
frost-evidence-gate status || true

# Persist a machine-readable monolith summary. This summary is observational;
# it never promotes DEVICE_VALIDATED/PERSISTENT_VALIDATED.
python - "${SUMMARY_JSON}" "${DEVICE_ID}" "${BOOT_ID}" "${ENROLLMENT_DIGEST}" \
  "${COMMISSION_ZIP}" "${OFFDEVICE_OK}" "${WORKER_OK}" "${CONTROLLER_OK}" \
  "${REBOOT_ARMED}" "${CONTROLLER_BUNDLE}" "${CONTROLLER_VERIFY}" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
(
    out, device_id, boot_id, enrollment_digest, commissioning_zip,
    offdevice, worker, controller, reboot_armed, controller_bundle,
    controller_verify,
) = sys.argv[1:]

def truth(v):
    return v.lower() == "true"

def file_sha(path):
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

summary = {
    "schema": "frost.evidence_gate.monolith_summary.v1",
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "device_id": device_id,
    "pre_reboot_boot_id": boot_id,
    "enrollment_digest": enrollment_digest,
    "commissioning_zip": commissioning_zip,
    "commissioning_zip_sha256": file_sha(commissioning_zip),
    "offdevice_roundtrip_observed": truth(offdevice),
    "bounded_worker_pass_observed": truth(worker),
    "controller_phase_a_verified_or_collected": truth(controller),
    "physical_reboot_continuation_armed": truth(reboot_armed),
    "controller_bundle": controller_bundle if Path(controller_bundle).is_file() else None,
    "controller_bundle_sha256": file_sha(controller_bundle),
    "controller_verification": controller_verify if Path(controller_verify).is_file() else None,
    "promotion_performed": False,
    "next_irreducible_action": "PHYSICAL_ANDROID_REBOOT" if truth(reboot_armed) else "COMPLETE_PENDING_EXTERNAL_CONFIGURATION",
}
Path(out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

say "Monolith complete through the current physical boundary"
printf 'Run log: %s\n' "${RUN_LOG}"
printf 'Summary: %s\n' "${SUMMARY_JSON}"
printf 'Commissioning ZIP: %s\n' "${COMMISSION_ZIP}"

if [ "${REBOOT_ARMED}" = true ]; then
  cat <<'EOF'

NEXT REQUIRED PHYSICAL ACTION
-----------------------------
Physically reboot the Android phone from its normal device UI.
Do NOT use adb reboot, remote shell reboot, or a simulated reboot.
The installed Termux:Boot continuation will collect the post-reboot local facts.
After Android/Termux has returned, run the same one-paste monolith again to
collect/verify the post-reboot controller records without exposing credentials.
EOF
else
  cat <<'EOF'

PENDING EXTERNAL INPUTS
-----------------------
The local commissioning evidence is preserved. Configure/provide the missing
worker, controller, or rclone information reported above, then paste the same
monolith again. No gate was promoted from missing evidence.
EOF
fi
