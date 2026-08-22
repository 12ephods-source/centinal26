#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export CENTINAL26_DRY_RUN="${CENTINAL26_DRY_RUN:-0}"
exec "$(dirname "$0")/CENTINAL26_AUTOPILOT_ONE_PASTE_INSTALLER_v2_0.sh" "$@"
