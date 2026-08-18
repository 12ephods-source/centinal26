#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO_RAW="https://raw.githubusercontent.com/12ephods-source/centinal26"
BASE_COMMIT="0013c697c4d500d8aff62564a562b167f6458c7a"
BASE_PATH="deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.sh"
BASE_BLOB="da696b4fbe58f6ece86a11a98a2bd6976daeea50"
ADAPTER_COMMIT="fa9e2a8c7185e84bc1ca0be90256eefc458656e2"
ADAPTER_PATH="deploy/termux/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"
ADAPTER_BLOB="0b5d7b00ce4d8dd0af0ca7a73dcc40124c1dc647"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}/centinal26-fleet-v1.6.$$"

say(){ printf '[frost-fleet-v1.6] %s\n' "$*"; }
die(){ printf '[frost-fleet-v1.6] ERROR: %s\n' "$*" >&2; exit 1; }
cleanup(){ rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on any Android phone." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."
for c in curl git; do
  command -v "$c" >/dev/null 2>&1 || pkg install -y "$c" || die "Could not install $c."
done
mkdir -p "$TMP_ROOT"

verify_git_blob(){
  local file="$1" expected="$2" size oid
  size="$(wc -c < "$file" | tr -d '[:space:]')"
  oid="$({ printf 'blob %s\0' "$size"; cat "$file"; } | git hash-object --stdin)"
  [[ "$oid" == "$expected" ]] || die "Content identity mismatch for $(basename "$file"): got $oid expected $expected"
}

fetch_verified(){
  local commit="$1" path="$2" blob="$3" out="$4"
  curl -fsSL "$REPO_RAW/$commit/$path" -o "$out" || die "Could not fetch immutable source $commit/$path"
  verify_git_blob "$out" "$blob"
  chmod 700 "$out"
  bash -n "$out" || die "Shell syntax validation failed for $path"
}

BASE="$TMP_ROOT/FROST_FLEET_BOOTSTRAP_v1.5.sh"
ADAPTER="$TMP_ROOT/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"

say "Fetching and verifying host-qualified v1.5 bootstrap."
fetch_verified "$BASE_COMMIT" "$BASE_PATH" "$BASE_BLOB" "$BASE"

say "Running capability-first fleet bootstrap."
bash "$BASE"

say "Fetching and verifying registered Android device-validation adapter."
fetch_verified "$ADAPTER_COMMIT" "$ADAPTER_PATH" "$ADAPTER_BLOB" "$ADAPTER"

say "Installing bounded device-validation capability into the authenticated fleet worker."
bash "$ADAPTER"

if command -v frost-fleet-worker-status >/dev/null 2>&1; then
  frost-fleet-worker-status || true
fi

cat <<'EOF'

FROST FLEET BOOTSTRAP v1.6 COMPLETE
routing: conversations/jobs -> required capability -> any eligible phone
remote bootstrap operations:
  system.health
  system.capabilities
  capability.ensure
  device.validation.status
  device.validation.ensure
  device.validation.verify
remote Android reboot: disabled
arbitrary remote shell: disabled
arbitrary remote source/path/package selection: disabled
persistence proof: remains bound to the physical executor that produced its pre-reboot checkpoint

A real Android reboot, when required by the campaign, must still be performed by the device user.
EOF
