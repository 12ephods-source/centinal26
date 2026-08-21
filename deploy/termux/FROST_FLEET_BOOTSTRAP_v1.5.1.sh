#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO_RAW="https://raw.githubusercontent.com/12ephods-source/centinal26"
WORKER_COMMIT="8db2f126b4f681e36f55eb668227cbb9c8747616"
WORKER_BLOB="6d061c4d704841972eaa1790888cea4f60816637"
PROVIDER_COMMIT="29a01b9a7432cc7a120c079d925eb3f86957d3b5"
PROVIDER_BLOB="0df8e008b85392a7c4768866d9b3987b9a909cfd"
FLEET_COMMIT="00e37d65db71616e7e964d2d9d7eb0ea33a6a058"
FLEET_BLOB="8333db986588250ee99b79ad25f22d6a5b135e29"
TMP_ROOT="${TMPDIR:-$PREFIX/tmp}/centinal26-fleet-v1.5.1.$$"

say(){ printf '[frost-fleet-v1.5.1] %s\n' "$*"; }
die(){ printf '[frost-fleet-v1.5.1] ERROR: %s\n' "$*" >&2; exit 1; }
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

fetch_verify_run(){
  local commit="$1"
  local path="$2"
  local expected_blob="$3"
  local out="$TMP_ROOT/$(basename "$path")"
  curl -fsSL "$REPO_RAW/$commit/$path" -o "$out" || die "Could not fetch immutable source $commit/$path"
  verify_git_blob "$out" "$expected_blob"
  chmod 700 "$out"
  bash -n "$out" || die "Shell syntax validation failed for $path"
  bash "$out"
}

say "Installing/authenticating bounded Base44 fleet worker."
fetch_verify_run "$WORKER_COMMIT" "deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh" "$WORKER_BLOB"

say "Installing bounded capability provider registry."
fetch_verify_run "$PROVIDER_COMMIT" "deploy/termux/FROST_CAPABILITY_PROVIDER_v1.0.sh" "$PROVIDER_BLOB"

say "Running capability-first physical bootstrap and persistence preparation."
fetch_verify_run "$FLEET_COMMIT" "deploy/termux/FROST_FLEET_BOOTSTRAP_v1.2.sh" "$FLEET_BLOB"

cat <<'EOF'

FROST FLEET BOOTSTRAP v1.5.1 COMPLETE
source integrity: immutable commit + expected Git blob identity verified before execution
routing: conversations/jobs -> required capability -> any eligible phone
provisioning: missing registered Termux capability -> hardcoded provider -> signed pkg install -> verifier -> retry
remote operations during bootstrap: system.health, system.capabilities, capability.ensure
arbitrary remote shell: disabled
arbitrary package names from jobs: disabled
device identity: execution provenance only
EOF
