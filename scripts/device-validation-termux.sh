#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CENTINAL26_HOME="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
export CENTINAL26_DEVICE_CAMPAIGN="${CENTINAL26_DEVICE_CAMPAIGN:-$CENTINAL26_HOME/device-validation/current}"
history_dir="$CENTINAL26_HOME/device-validation/history"
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
command -v python >/dev/null 2>&1 || fail "Python is not available in Termux"
command -v git >/dev/null 2>&1 || fail "Git is not available in Termux"
[[ -d "$repo_root/.git" ]] || fail "campaign source is not a Git checkout: $repo_root"

source_sha="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null)" || fail "cannot resolve campaign source commit"
[[ -n "$source_sha" ]] || fail "campaign source commit is empty"
[[ -z "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]] || \
  fail "campaign source checkout is dirty; refusing mutable physical evidence"

python_bin="$(command -v python)"
git_bin="$(command -v git)"
mkdir -p "$history_dir" "$log_dir" "$boot_dir"

export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
export CENTINAL26_CAMPAIGN_SOURCE_SHA="$source_sha"

# Preserve incomplete evidence unchanged. Archive only a campaign that independently verifies.
if [[ -e "$CENTINAL26_DEVICE_CAMPAIGN" ]]; then
  if "$python_bin" -S -m centinal26.device_campaign_cli verify \
      --campaign "$CENTINAL26_DEVICE_CAMPAIGN" >/dev/null 2>&1; then
    archived="$history_dir/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$CENTINAL26_DEVICE_CAMPAIGN")"
    mv "$CENTINAL26_DEVICE_CAMPAIGN" "$archived"
    printf 'Archived prior verified campaign: %s\n' "$archived"
  else
    fail "an incomplete or invalid campaign already exists at $CENTINAL26_DEVICE_CAMPAIGN; preserving it unchanged for diagnosis"
  fi
fi

printf -v q_source '%q' "$repo_root"
printf -v q_sha '%q' "$source_sha"
printf -v q_campaign '%q' "$CENTINAL26_DEVICE_CAMPAIGN"
printf -v q_python '%q' "$python_bin"
printf -v q_git '%q' "$git_bin"
printf -v q_hook '%q' "$boot_hook"
printf -v q_log '%q' "$log_dir/device-campaign-boot.log"

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
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
"\$PYTHON_BIN" -S -m centinal26.device_campaign_cli resume \
  --campaign "\$CAMPAIGN" \
  --boot-hook "\$BOOT_HOOK" \
  >>"\$LOG_FILE" 2>&1
EOF
chmod 700 "$boot_hook"
bash -n "$boot_hook"

printf 'Campaign source commit: %s\n' "$source_sha"
printf 'Dedicated Termux:Boot campaign hook: %s\n' "$boot_hook"
printf 'Canonical daemon boot hook is not modified by this campaign.\n'

"$python_bin" -S -m compileall -q "$repo_root/src"
"$python_bin" -S -m centinal26.device_campaign_cli prepare \
  --campaign "$CENTINAL26_DEVICE_CAMPAIGN" \
  --boot-hook "$boot_hook"

cat <<EOF

PRE-REBOOT PHASE: PASS
Campaign: $CENTINAL26_DEVICE_CAMPAIGN
Source commit: $source_sha
Campaign boot hook: $boot_hook

Required physical action: reboot Android once.
After Android starts, Termux:Boot must run the dedicated campaign hook. The hook will refuse a changed or dirty source checkout, require a changed kernel boot_id, re-verify the pre-reboot evidence, execute a second authorized canonical probe, and write the final device-validation report and SHA-256 manifest.

After reboot, independently inspect with:
  export PYTHONPATH="$repo_root/src\${PYTHONPATH:+:\$PYTHONPATH}"
  python -S -m centinal26.device_campaign_cli verify --campaign "$CENTINAL26_DEVICE_CAMPAIGN"

A successful pre-reboot run alone is NOT persistence validation.
EOF
