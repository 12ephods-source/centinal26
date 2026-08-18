#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO_RAW="https://raw.githubusercontent.com/12ephods-source/centinal26"
BASE_COMMIT="fdad8cdab27471e6192abc423707bf5cebd4d449"
BASE_PATH="deploy/termux/FROST_FLEET_BOOTSTRAP_v1.5.1.sh"
BASE_BLOB="23d2b4c9f3648642eb7ad5a9d93da51db9d05d56"
ADAPTER_COMMIT="fa9e2a8c7185e84bc1ca0be90256eefc458656e2"
ADAPTER_PATH="deploy/termux/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"
ADAPTER_BLOB="0b5d7b00ce4d8dd0af0ca7a73dcc40124c1dc647"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}/centinal26-fleet-v1.7.$$"

say(){ printf '[frost-fleet-v1.7] %s\n' "$*"; }
die(){ printf '[frost-fleet-v1.7] ERROR: %s\n' "$*" >&2; exit 1; }
cleanup(){ rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on any Android phone." ;;
esac
command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."
missing=()
command -v curl >/dev/null 2>&1 || missing+=(curl)
command -v sha1sum >/dev/null 2>&1 || missing+=(coreutils)
if ((${#missing[@]})); then pkg install -y "${missing[@]}" || die "Could not install bootstrap verification tools."; fi
mkdir -p "$TMP_ROOT"

verify_git_blob(){
  local file="$1" expected="$2" size actual
  size="$(wc -c < "$file" | tr -d '[:space:]')"
  actual="$( { printf 'blob %s\0' "$size"; cat "$file"; } | sha1sum | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || die "Git blob identity mismatch for $(basename "$file"): expected=$expected actual=$actual"
}

fetch_verified(){
  local commit="$1"
  local path="$2"
  local blob="$3"
  local out="$4"
  curl -fsSL "$REPO_RAW/$commit/$path" -o "$out" || die "Could not fetch immutable source $commit/$path"
  verify_git_blob "$out" "$blob"
  chmod 700 "$out"
  bash -n "$out" || die "Shell syntax validation failed for $path"
}

BASE="$TMP_ROOT/FROST_FLEET_BOOTSTRAP_v1.5.1.sh"
ADAPTER="$TMP_ROOT/FROST_DEVICE_VALIDATION_ADAPTER_v1.0.sh"

say "Fetching and verifying nounset-safe fleet bootstrap v1.5.1."
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

FROST FLEET BOOTSTRAP v1.7 COMPLETE
physical defect fixed: nounset-safe immutable fetch helper
source integrity: immutable commit + expected Git blob identity verified before execution
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
