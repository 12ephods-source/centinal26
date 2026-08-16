#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

export CENTINAL26_HOME="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
termux-wake-lock >/dev/null 2>&1 || true

campaign="${CENTINAL26_DEVICE_CAMPAIGN:-$CENTINAL26_HOME/device-validation/current}"
log_dir="$CENTINAL26_HOME/logs"
mkdir -p "$log_dir"

if [[ -f "$campaign/device-campaign-checkpoint.json" && ! -f "$campaign/device-validation-report.json" ]]; then
  python -m centinal26.device_campaign_cli resume \
    --campaign "$campaign" \
    --boot-hook "$HOME/.termux/boot/centinal26.sh" \
    >>"$log_dir/device-campaign-boot.log" 2>&1 || true
fi

exec centinal26 auto-daemon --poll "${CENTINAL26_POLL_SECONDS:-2}"
