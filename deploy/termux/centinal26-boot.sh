#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

export CENTINAL26_HOME="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
termux-wake-lock >/dev/null 2>&1 || true
exec centinal26 auto-daemon --poll "${CENTINAL26_POLL_SECONDS:-2}"
