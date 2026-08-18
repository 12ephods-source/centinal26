#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CENTINAL26_HOME="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
log_dir="$CENTINAL26_HOME/logs"
boot_dir="$HOME/.termux/boot"
boot_hook="$boot_dir/centinal26-device-campaign.sh"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

if [[ "${PREFIX:-}" != *com.termux* ]]; then
  fail "this campaign must run inside Termux"
fi

# Capability convergence: install missing phone-local prerequisites instead of
# rejecting a usable phone merely because its Termux environment is incomplete.
missing_packages=()
need_package() {
  local command_name="$1" package_name="$2"
  command -v "$command_name" >/dev/null 2>&1 || missing_packages+=("$package_name")
}
need_package python python
need_package git git
need_package sha256sum coreutils

if [[ "${#missing_packages[@]}" -gt 0 ]]; then
  command -v pkg >/dev/null 2>&1 || \
    fail "Termux package manager is unavailable; cannot add missing requirements: ${missing_packages[*]}"
  printf 'Installing missing Termux requirements: %s\n' "${missing_packages[*]}"
  pkg install -y "${missing_packages[@]}" || \
    fail "Termux could not install required packages: ${missing_packages[*]}"
fi

command -v python >/dev/null 2>&1 || fail "Python is still unavailable after provisioning"
command -v git >/dev/null 2>&1 || fail "Git is still unavailable after provisioning"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is still unavailable after provisioning"
[[ -d "$repo_root/.git" ]] || fail "campaign source is not a Git checkout: $repo_root"

source_sha="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null)" || fail "cannot resolve campaign source commit"
[[ -n "$source_sha" ]] || fail "campaign source commit is empty"
[[ -z "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]] || \
  fail "campaign source checkout is dirty; refusing mutable physical evidence"

python_bin="$(command -v python)"
git_bin="$(command -v git)"
mkdir -p "$log_dir" "$boot_dir"

export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
export CENTINAL26_CAMPAIGN_SOURCE_SHA="$source_sha"

# Resolve this phone's durable identity only for provenance/evidence. Jobs and
# conversations are capability-routed and are not pinned to this identity.
identity_json="$("$python_bin" -S -m centinal26.device_campaign_cli identity)" || \
  fail "cannot establish local device identity"
device_id="$(printf '%s' "$identity_json" | "$python_bin" -c 'import json,sys; print(json.load(sys.stdin)["device_id"])')" || \
  fail "cannot parse local device identity"
[[ -n "$device_id" ]] || fail "local device identity is empty"
export AUTOMATION_DEVICE_ID="$device_id"

# Each phone gets its own local persistence campaign slot. This prevents one
# phone's unfinished reboot evidence from blocking work on another phone while
# keeping every persistence proof bound to the device that actually ran it.
if [[ -z "${CENTINAL26_DEVICE_CAMPAIGN:-}" ]]; then
  export CENTINAL26_DEVICE_CAMPAIGN="$CENTINAL26_HOME/device-validation/devices/$device_id/current"
fi
history_dir="$CENTINAL26_HOME/device-validation/devices/$device_id/history"
mkdir -p "$history_dir"

# Preserve incomplete evidence unchanged. Archive only a campaign that
# independently verifies on this same physical phone identity.
if [[ -e "$CENTINAL26_DEVICE_CAMPAIGN" ]]; then
  if "$python_bin" -S -m centinal26.device_campaign_cli verify \
      --campaign "$CENTINAL26_DEVICE_CAMPAIGN" >/dev/null 2>&1; then
    archived="$history_dir/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$CENTINAL26_DEVICE_CAMPAIGN")"
    mv "$CENTINAL26_DEVICE_CAMPAIGN" "$archived"
    printf 'Archived prior verified campaign: %s\n' "$archived"
  else
    fail "an incomplete or invalid campaign already exists for this phone at $CENTINAL26_DEVICE_CAMPAIGN; preserving it unchanged for diagnosis"
  fi
fi

printf -v q_source '%q' "$repo_root"
printf -v q_sha '%q' "$source_sha"
printf -v q_campaign '%q' "$CENTINAL26_DEVICE_CAMPAIGN"
printf -v q_python '%q' "$python_bin"
printf -v q_git '%q' "$git_bin"
printf -v q_hook '%q' "$boot_hook"
printf -v q_log '%q' "$log_dir/device-campaign-boot.log"
printf -v q_device '%q' "$device_id"

cat > "$boot_hook" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
SOURCE_DIR=$q_source
SOURCE_SHA=$q_sha
CAMPAIGN=$q_campaign
PYTHON_BIN=$q_python
GIT_BIN=$q_git
BOOT_HOOK=$q_hook
LOG_FILE=$q_log
DEVICE_ID=$q_device

mkdir -p "\$(dirname "\$LOG_FILE")"
actual="\$("\$GIT_BIN" -C "\$SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)"
if [[ "\$actual" != "\$SOURCE_SHA" ]]; then
  printf 'SOURCE_PIN_MISMATCH expected=%s actual=%s\n' "\$SOURCE_SHA" "\$actual" >>"\$LOG_FILE"
  exit 74
fi
if [[ -n "\$("\$GIT_BIN" -C "\$SOURCE_DIR" status --porcelain --untracked-files=all)" ]]; then
  printf 'SOURCE_DIRTY refusing persistence resume\n' >>"\$LOG_FILE"
  exit 75
fi

export PYTHONPATH="\$SOURCE_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
export CENTINAL26_CAMPAIGN_SOURCE_SHA="\$SOURCE_SHA"
export AUTOMATION_DEVICE_ID="\$DEVICE_ID"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
"\$PYTHON_BIN" -S -m centinal26.device_campaign_cli resume \
  --campaign "\$CAMPAIGN" \
  --boot-hook "\$BOOT_HOOK" \
  >>"\$LOG_FILE" 2>&1
EOF
chmod 700 "$boot_hook"
bash -n "$boot_hook"

printf 'Execution phone identity: %s\n' "$device_id"
printf 'Campaign source commit: %s\n' "$source_sha"
printf 'Per-phone campaign: %s\n' "$CENTINAL26_DEVICE_CAMPAIGN"
printf 'Dedicated Termux:Boot campaign hook: %s\n' "$boot_hook"
printf 'Canonical daemon boot hook is not modified by this campaign.\n'

"$python_bin" -S -m compileall -q "$repo_root/src"
"$python_bin" -S -m centinal26.device_campaign_cli prepare \
  --campaign "$CENTINAL26_DEVICE_CAMPAIGN" \
  --boot-hook "$boot_hook"

cat <<EOF

PRE-REBOOT PHASE: PASS
Device identity: $device_id
Campaign: $CENTINAL26_DEVICE_CAMPAIGN
Source commit: $source_sha
Campaign boot hook: $boot_hook

Required physical action: reboot this Android phone once.
After Android starts, Termux:Boot must run the dedicated campaign hook. The hook will refuse a changed or dirty source checkout, require the same persistent phone identity with a changed kernel boot_id, re-verify the pre-reboot evidence, execute a second authorized canonical probe, and write the final device-validation report and SHA-256 manifest.

Other phones remain free to claim capability-compatible work and use their own local campaign slots; conversations and jobs are not pinned to this phone.

After reboot, independently inspect with:
  export PYTHONPATH="$repo_root/src\${PYTHONPATH:+:\$PYTHONPATH}"
  export AUTOMATION_DEVICE_ID="$device_id"
  python -S -m centinal26.device_campaign_cli verify --campaign "$CENTINAL26_DEVICE_CAMPAIGN"

A successful pre-reboot run alone is NOT persistence validation.
EOF
