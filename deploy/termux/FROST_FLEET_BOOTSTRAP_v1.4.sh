#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO_RAW="https://raw.githubusercontent.com/12ephods-source/centinal26"
WORKER_COMMIT="8db2f126b4f681e36f55eb668227cbb9c8747616"
PROVIDER_COMMIT="29a01b9a7432cc7a120c079d925eb3f86957d3b5"
FLEET_COMMIT="00e37d65db71616e7e964d2d9d7eb0ea33a6a058"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}/centinal26-fleet-v1.4.$$"

say(){ printf '[frost-fleet-v1.4] %s\n' "$*"; }
die(){ printf '[frost-fleet-v1.4] ERROR: %s\n' "$*" >&2; exit 1; }
cleanup(){ rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on any Android phone." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."
if ! command -v curl >/dev/null 2>&1; then pkg install -y curl || die "Could not install curl."; fi
mkdir -p "$TMP_ROOT"

fetch_run(){
  local commit="$1" path="$2" out="$TMP_ROOT/$(basename "$path")"
  curl -fsSL "$REPO_RAW/$commit/$path" -o "$out" || die "Could not fetch immutable source $commit/$path"
  chmod 700 "$out"
  bash -n "$out" || die "Shell syntax validation failed for $path"
  bash "$out"
}

say "Installing/authenticating bounded Base44 fleet worker."
fetch_run "$WORKER_COMMIT" "deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh"

say "Installing bounded capability provider registry."
fetch_run "$PROVIDER_COMMIT" "deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh"

say "Running capability-first physical bootstrap and persistence preparation."
fetch_run "$FLEET_COMMIT" "deploy/termux/FROST_FLEET_BOOTSTRAP_v1.2.sh"

cat <<'EOF'

FROST FLEET BOOTSTRAP v1.4 COMPLETE
routing: conversations/jobs -> required capability -> any eligible phone
provisioning: missing registered Termux capability -> hardcoded provider -> signed pkg install -> verifier -> retry
remote operations during bootstrap: system.health, system.capabilities, capability.ensure
arbitrary remote shell: disabled
arbitrary package names from jobs: disabled
device identity: execution provenance only
EOF
