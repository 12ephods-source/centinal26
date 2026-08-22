#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

ROOT="${AUTOMATION_BRIDGE_ROOT:-$HOME/.automation_bridge}"
CFG="$ROOT/bridge.env"
START="$HOME/.local/bin/frost-fleet-worker-start"
STATUS="$HOME/.local/bin/frost-fleet-worker-status"
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
BOOTSTRAP="$REPO/deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh"
MODE="${1:---recover}"

emit() { printf '%s\n' "$1"; }

case "$MODE" in
  --self-test)
    [[ "$ROOT" != "/" ]]
    [[ "$START" == "$HOME/.local/bin/frost-fleet-worker-start" ]]
    [[ "$BOOTSTRAP" == "$REPO/deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh" ]]
    grep -q 'WORKER_RECOVERY_AUTH_REQUIRED' "$0"
    ! grep -Eq 'cat[[:space:]]+.*bridge\.env|printf.*BASE44_TOKEN|echo.*BASE44_TOKEN' "$0"
    grep -q 'bash "$BOOTSTRAP" </dev/null' "$0"
    emit 'WORKER_AUTORECOVER_SELF_TEST=PASS'
    exit 0
    ;;
  --recover) ;;
  *) emit 'usage: FROST_WORKER_AUTORECOVER_v1.0.sh [--recover|--self-test]'; exit 2 ;;
esac

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) emit 'WORKER_RECOVERY_NOT_ANDROID_TERMUX'; exit 10 ;;
esac

# A credential file is necessary but never copied, printed, or modified here.
if [[ ! -s "$CFG" ]]; then
  emit 'WORKER_RECOVERY_AUTH_REQUIRED'
  exit 20
fi
chmod 600 "$CFG" 2>/dev/null || true

# If the bounded worker is already healthy, recovery is idempotent.
if [[ -x "$STATUS" ]] && "$STATUS" 2>/dev/null | head -n 1 | grep -q '^RUNNING'; then
  emit 'WORKER_RECOVERY_ALREADY_RUNNING'
  exit 0
fi

# If installed but stopped, restart without reprovisioning.
if [[ -x "$START" ]]; then
  if "$START" >/dev/null 2>&1; then
    emit 'WORKER_RECOVERY_RESTARTED'
    exit 0
  fi
fi

# If local credentials exist but worker machinery is missing/broken, reinstall only
# from the trusted, repository-controlled bounded bootstrap. stdin is closed so a
# daemon can never fall into an interactive credential prompt.
if [[ -f "$BOOTSTRAP" ]]; then
  if bash "$BOOTSTRAP" </dev/null >/dev/null 2>&1; then
    if [[ -x "$START" ]] && "$START" >/dev/null 2>&1; then
      emit 'WORKER_RECOVERY_REINSTALLED_AND_STARTED'
      exit 0
    fi
  fi
fi

emit 'WORKER_RECOVERY_FAILED_PRESERVED'
exit 30
