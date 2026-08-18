#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

BRIDGE_COMMIT="81bdbfacdd19f9041b34dace15756d62f8a777c6"
FLEET_COMMIT="00e37d65db71616e7e964d2d9d7eb0ea33a6a058"
REPO_RAW="https://raw.githubusercontent.com/12ephods-source/centinal26"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}/frost-fleet-bootstrap-v1.3"
BRIDGE="$TMP_ROOT/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh"
FLEET="$TMP_ROOT/FROST_FLEET_BOOTSTRAP_v1.2.sh"

say(){ printf '[frost-fleet-v1.3] %s\n' "$*"; }
die(){ printf '[frost-fleet-v1.3] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on any available Android phone." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."

if ! command -v curl >/dev/null 2>&1; then
  pkg install -y curl || die "Could not install curl."
fi
mkdir -p "$TMP_ROOT"
chmod 700 "$TMP_ROOT"

say "Installing/recovering the bounded Base44 fleet worker."
curl -fsSL "$REPO_RAW/$BRIDGE_COMMIT/deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh" -o "$BRIDGE" || die "Could not fetch the pinned Base44 worker bootstrap."
chmod 700 "$BRIDGE"
bash -n "$BRIDGE" || die "Base44 worker bootstrap syntax check failed."
set +e
bash "$BRIDGE"
bridge_rc=$?
set -e
if [[ "$bridge_rc" -eq 20 ]]; then
  cat <<'EOF'
Base44 worker software is installed far enough to identify the remaining boundary,
but this non-interactive run has no device-side Base44 credential.
Rerun this script interactively in Termux, or export one of:
  BASE44_TOKEN + BASE44_WORKER_EMAIL
  BASE44_EMAIL + BASE44_PASSWORD
Credentials are stored only in ~/.automation_bridge/bridge.env with mode 600.
EOF
  exit 20
fi
[[ "$bridge_rc" -eq 0 ]] || die "Base44 worker bootstrap failed with rc=$bridge_rc"

say "Running the previously host-qualified capability-first physical bootstrap."
curl -fsSL "$REPO_RAW/$FLEET_COMMIT/deploy/termux/FROST_FLEET_BOOTSTRAP_v1.2.sh" -o "$FLEET" || die "Could not fetch the pinned fleet bootstrap."
chmod 700 "$FLEET"
bash -n "$FLEET" || die "Fleet bootstrap syntax check failed."
bash "$FLEET"

say "Fleet bootstrap complete."
if command -v frost-fleet-worker-status >/dev/null 2>&1; then
  frost-fleet-worker-status || true
fi
cat <<'EOF'
Routing policy:
  conversations/jobs -> required capability -> any eligible phone
Device identity is retained only for provenance, reboot proof, and audit.
EOF
