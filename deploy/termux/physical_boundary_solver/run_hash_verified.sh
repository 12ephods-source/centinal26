#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

DIR="$(cd "$(dirname "$0")" && pwd)"
SOLVER="${FROST_SOLVER_BIN:-$DIR/run.sh}"
STATE_HOME="${FROST_BOUNDARY_HOME:-$HOME/.local/share/frost-physical-boundary-solver}"
VERIFY_HOME="$STATE_HOME/hash-verified"
mkdir -p "$VERIFY_HOME"

if [ -d "$HOME/storage/downloads" ]; then
  DEFAULT_EVIDENCE_ROOT="$HOME/storage/downloads/FrostForgePhysicalBoundaryEvidence"
else
  DEFAULT_EVIDENCE_ROOT="$HOME/FrostForgePhysicalBoundaryEvidence"
fi
EVIDENCE_ROOT="${EVIDENCE_ROOT:-$DEFAULT_EVIDENCE_ROOT}"

write_status() {
  local status="$1"
  local detail="${2:-}"
  local zip_path="${3:-}"
  local digest="${4:-}"
  cat > "$VERIFY_HOME/status.json" <<EOF
{
  "schema": "frost.physical_boundary_solver.hash_verified.v1",
  "status": "$status",
  "detail": "$detail",
  "evidence_zip": "$zip_path",
  "sha256": "$digest"
}
EOF
  cat "$VERIFY_HOME/status.json"
}

set +e
bash "$SOLVER" --run
solver_rc=$?
set -e

if [ "$solver_rc" -ne 0 ]; then
  write_status "SOLVER_NOT_TERMINAL" "canonical solver returned rc=$solver_rc; no physical promotion" "" ""
  exit "$solver_rc"
fi

solver_status="$(sed -n 's/.*"status": "\([^"]*\)".*/\1/p' "$STATE_HOME/status.json" | head -1)"
case "$solver_status" in
  PHYSICAL_CLEANER_PROOF_DELETE_VERIFIED_LOCALLY)
    terminal="REAL_DEVICE_EXECUTED_EVIDENCE_PRESERVED_HASH_VERIFIED"
    ;;
  PHYSICAL_CLEANER_INSTALLED_QUALIFIED_NO_DELETE_NEEDED)
    terminal="REAL_DEVICE_QUALIFIED_NO_DELETE_EVIDENCE_PRESERVED_HASH_VERIFIED"
    ;;
  *)
    write_status "SOLVER_STATUS_NOT_PROMOTABLE" "solver status=$solver_status" "" ""
    exit 30
    ;;
esac

latest="$(find "$EVIDENCE_ROOT" -maxdepth 1 -type f -name 'FrostForgePhysicalBoundaryEvidence_*.zip' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
if [ -z "$latest" ] || [ ! -f "$latest" ]; then
  write_status "EVIDENCE_ZIP_MISSING" "solver completed but no evidence ZIP was found" "" ""
  exit 31
fi

sidecar="$latest.sha256"
if [ ! -f "$sidecar" ]; then
  write_status "EVIDENCE_SIDECAR_MISSING" "evidence ZIP exists but SHA-256 sidecar is missing" "$latest" ""
  exit 32
fi

expected="$(awk 'NR==1 {print $1}' "$sidecar")"
actual="$(sha256sum "$latest" | awk '{print $1}')"
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
  write_status "EVIDENCE_HASH_MISMATCH" "device-side SHA-256 verification failed" "$latest" "$actual"
  exit 33
fi

printf '%s  %s\n' "$actual" "$(basename "$latest")" > "$VERIFY_HOME/verified-evidence.sha256"
write_status "$terminal" "canonical solver completed and device evidence hash matched its sidecar" "$latest" "$actual"
