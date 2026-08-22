#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

VERSION="1.0.0"
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
STATE="${FROST_WORKER_RECOVERY_STATE:-$HOME/.frost_worker_recovery}"
BIN="$HOME/.local/bin"
INTERVAL="${FROST_WORKER_RECOVERY_INTERVAL:-3600}"
HELPER="$REPO/deploy/termux/FROST_WORKER_AUTORECOVER_v1.0.sh"
NO_DAEMON="${FROST_NO_DAEMON:-0}"
MODE="install"

for arg in "$@"; do
  case "$arg" in
    --self-test) MODE="self-test" ;;
    --no-daemon) NO_DAEMON=1 ;;
    --version) printf '%s\n' "$VERSION"; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

if [[ "$MODE" == "self-test" ]]; then
  bash "$HELPER" --self-test
  grep -q 'WORKER_RECOVERY_AUTH_REQUIRED' "$HELPER"
  grep -q 'WORKER_RECOVERY_RESTARTED' "$HELPER"
  grep -q 'WORKER_RECOVERY_REINSTALLED_AND_STARTED' "$HELPER"
  printf 'WORKER_AUTORECOVERY_INSTALLER_SELF_TEST=PASS\n'
  exit 0
fi

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) printf 'ERROR: run inside Android/Termux\n' >&2; exit 10 ;;
esac
[[ -f "$HELPER" ]] || { printf 'ERROR: missing helper %s\n' "$HELPER" >&2; exit 2; }
mkdir -p "$STATE" "$BIN" "$HOME/.termux/boot"
chmod 700 "$STATE" "$BIN" "$HOME/.termux/boot" 2>/dev/null || true

RUNNER="$BIN/frost-worker-autorecover"
cat > "$RUNNER" <<'RUNNER_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
STATE="${FROST_WORKER_RECOVERY_STATE:-$HOME/.frost_worker_recovery}"
HELPER="$REPO/deploy/termux/FROST_WORKER_AUTORECOVER_v1.0.sh"
mkdir -p "$STATE"
set +e
out="$(bash "$HELPER" --recover 2>&1)"
rc=$?
set -e
printf '[%s] rc=%s result=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" "$out" >> "$STATE/recovery.log"
printf '%s\n' "$out"
exit "$rc"
RUNNER_EOF
chmod 700 "$RUNNER"

LOOP="$BIN/frost-worker-autorecover-loop"
cat > "$LOOP" <<'LOOP_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
INTERVAL="${FROST_WORKER_RECOVERY_INTERVAL:-3600}"
while :; do
  "$HOME/.local/bin/frost-worker-autorecover" >/dev/null 2>&1 || true
  sleep "$INTERVAL"
done
LOOP_EOF
chmod 700 "$LOOP"

BOOT="$HOME/.termux/boot/frost-worker-autorecover.sh"
cat > "$BOOT" <<'BOOT_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
export PATH="$HOME/.local/bin:${PREFIX:-/data/data/com.termux/files/usr}/bin:$PATH"
if ! pgrep -f "$HOME/.local/bin/frost-worker-autorecover-loop" >/dev/null 2>&1; then
  nohup "$HOME/.local/bin/frost-worker-autorecover-loop" >>"$HOME/.frost_worker_recovery/boot.log" 2>&1 &
fi
BOOT_EOF
chmod 700 "$BOOT"

# Attempt recovery immediately. AUTH_REQUIRED and other preserved failures are not
# promoted to success; the loop will retry after legitimate local credentials exist.
"$RUNNER" || true

if [[ "$NO_DAEMON" != 1 ]] && ! pgrep -f "$LOOP" >/dev/null 2>&1; then
  nohup "$LOOP" >>"$STATE/daemon.log" 2>&1 &
fi
printf 'Worker autorecovery v%s installed\n' "$VERSION"
