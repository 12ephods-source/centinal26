#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CENTINAL26_HOME="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
export CENTINAL26_DEVICE_CAMPAIGN="${CENTINAL26_DEVICE_CAMPAIGN:-$CENTINAL26_HOME/device-validation/current}"
boot_hook="$HOME/.termux/boot/centinal26.sh"
history_dir="$CENTINAL26_HOME/device-validation/history"

if [[ "${PREFIX:-}" != *com.termux* ]] || [[ -z "${ANDROID_ROOT:-}" ]]; then
  printf 'ERROR: this campaign must run inside Termux on Android.\n' >&2
  exit 2
fi
if ! command -v python >/dev/null 2>&1; then
  printf 'ERROR: Python is not available in Termux.\n' >&2
  exit 2
fi

python -m pip install -e "$repo_root"
bash "$repo_root/scripts/enable-termux-boot.sh"

if git -C "$repo_root" rev-parse HEAD >/dev/null 2>&1; then
  export CENTINAL26_CAMPAIGN_SOURCE_SHA="$(git -C "$repo_root" rev-parse HEAD)"
fi

if [[ -e "$CENTINAL26_DEVICE_CAMPAIGN" ]]; then
  if python -m centinal26.device_campaign_cli verify \
      --campaign "$CENTINAL26_DEVICE_CAMPAIGN" >/dev/null 2>&1; then
    mkdir -p "$history_dir"
    archived="$history_dir/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$CENTINAL26_DEVICE_CAMPAIGN")"
    mv "$CENTINAL26_DEVICE_CAMPAIGN" "$archived"
    printf 'Archived prior verified campaign: %s\n' "$archived"
  else
    printf 'ERROR: an incomplete or invalid campaign already exists at %s\n' \
      "$CENTINAL26_DEVICE_CAMPAIGN" >&2
    printf 'Preserving it unchanged for diagnosis; choose another CENTINAL26_DEVICE_CAMPAIGN path to start a new run.\n' >&2
    exit 2
  fi
fi

python -m centinal26.device_campaign_cli prepare \
  --campaign "$CENTINAL26_DEVICE_CAMPAIGN" \
  --boot-hook "$boot_hook"

cat <<EOF

PRE-REBOOT PHASE: PASS
Campaign: $CENTINAL26_DEVICE_CAMPAIGN
Boot hook: $boot_hook

Required physical action: reboot Android once.
After Android starts, Termux:Boot will automatically resume the same campaign, require a changed kernel boot_id, re-verify the pre-reboot evidence, execute a second authorized canonical probe, and write the final device-validation report and SHA-256 manifest.

After reboot, inspect with:
  python -m centinal26.device_campaign_cli verify --campaign "$CENTINAL26_DEVICE_CAMPAIGN"

A successful pre-reboot run alone is NOT persistence validation.
EOF
