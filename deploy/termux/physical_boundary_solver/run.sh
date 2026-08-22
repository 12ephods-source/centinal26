#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

VERSION="1.0.0"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CLEANER_DIR="$ROOT/deploy/termux/library_cleaner"
STATE_HOME="${FROST_BOUNDARY_HOME:-$HOME/.local/share/frost-physical-boundary-solver}"
RUN_HOME="$STATE_HOME/runs"
LOCK="$STATE_HOME/lock"
APP="$HOME/.local/share/frost-library-cleaner"
SERVICE="${PREFIX:-/nontermux}/var/service/frost-library-cleaner"
mkdir -p "$STATE_HOME" "$RUN_HOME"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$STATE_HOME/solver.log" >&2
}

write_status() {
  local status="$1"
  local detail="${2:-}"
  local now
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat > "$STATE_HOME/status.json" <<EOF
{
  "schema": "frost.physical_boundary_solver.state.v1",
  "status": "$status",
  "detail": "$detail",
  "solver_version": "$VERSION",
  "updated_utc": "$now"
}
EOF
  cat "$STATE_HOME/status.json"
}

is_real_termux() {
  [ -n "${PREFIX:-}" ] || return 1
  case "$PREFIX" in
    /data/data/*/files/usr) ;;
    *) return 1 ;;
  esac
  command -v getprop >/dev/null 2>&1 || return 1
  [ -n "$(getprop ro.build.version.release 2>/dev/null || true)" ] || return 1
}

repair_termux_packages() {
  local key_commit="625e1c90f5110842ec5d2e1fda677abdb5edfbed"
  local key_sha="21c385d5a30107453bd60582d64e2f6e5f5ce11e340ac05e57f943f9c0235420"
  local key_url="https://raw.githubusercontent.com/termux/termux-packages/${key_commit}/packages/termux-keyring/termux-autobuilds.gpg"
  local keydir="${PREFIX}/etc/apt/trusted.gpg.d"
  local tmp="${TMPDIR:-${PREFIX}/tmp}/frost-termux-autobuilds.gpg"
  command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null 2>&1 || return 1
  mkdir -p "$keydir" "$(dirname "$tmp")"
  curl -fsSL "$key_url" -o "$tmp"
  printf '%s  %s\n' "$key_sha" "$tmp" | sha256sum -c -
  install -m 600 "$tmp" "$keydir/termux-autobuilds.gpg"
  pkg update -y
}

ensure_dependencies() {
  if pkg install -y python coreutils android-tools termux-services curl >/dev/null; then
    return 0
  fi
  log "initial package install failed; attempting pinned keyring recovery"
  repair_termux_packages
  pkg install -y python coreutils android-tools termux-services curl >/dev/null
}

try_adb_reconnect() {
  command -v adb >/dev/null 2>&1 || return 1
  adb start-server >/dev/null 2>&1 || true
  if [ "$(adb get-state 2>/dev/null || true)" = "device" ]; then return 0; fi
  local services endpoints ep
  services="$(adb mdns services 2>/dev/null || true)"
  endpoints="$(printf '%s\n' "$services" | grep -Eo '(([0-9]{1,3}\.){3}[0-9]{1,3}|localhost|127\.0\.0\.1):[0-9]+' | sort -u || true)"
  for ep in $endpoints; do
    adb connect "$ep" >/dev/null 2>&1 || true
    [ "$(adb get-state 2>/dev/null || true)" = "device" ] && return 0
  done
  return 1
}

capture_profile() {
  local out="$1"
  python - "$out" <<'PY'
import datetime, hashlib, json, os, pathlib, platform, subprocess, sys
def cmd(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=15,check=False)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None
boot=None
try: boot=pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()
except OSError: pass
data={
 "schema":"frost.physical_boundary_solver.device.v1",
 "captured_utc":datetime.datetime.now(datetime.UTC).isoformat(),
 "manufacturer":cmd(["getprop","ro.product.manufacturer"]),
 "model":cmd(["getprop","ro.product.model"]),
 "android_version":cmd(["getprop","ro.build.version.release"]),
 "android_sdk":cmd(["getprop","ro.build.version.sdk"]),
 "architecture":platform.machine(),
 "kernel":platform.release(),
 "termux_version":os.environ.get("TERMUX_VERSION"),
 "prefix":os.environ.get("PREFIX"),
 "boot_id":boot,
}
canonical=json.dumps(data,sort_keys=True,separators=(",",":")).encode()
data["record_sha256"]=hashlib.sha256(canonical).hexdigest()
pathlib.Path(sys.argv[1]).write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
PY
}

package_evidence() {
  local run="$1"
  local outdir="${EVIDENCE_ROOT:-$HOME/FrostForgePhysicalBoundaryEvidence}"
  mkdir -p "$outdir"
  local stamp zip
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  zip="$outdir/FrostForgePhysicalBoundaryEvidence_${stamp}.zip"
  python - "$run" "$zip" <<'PY'
import hashlib, json, pathlib, sys, zipfile
root=pathlib.Path(sys.argv[1]); zp=pathlib.Path(sys.argv[2])
files=sorted(p for p in root.rglob("*") if p.is_file())
records=[{"path":str(p.relative_to(root)),"size":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
    for p in files: z.write(p,arcname=str(p.relative_to(root)))
    z.writestr("EVIDENCE_MANIFEST.json",json.dumps(records,indent=2,sort_keys=True)+"\n")
digest=hashlib.sha256(zp.read_bytes()).hexdigest()
pathlib.Path(str(zp)+".sha256").write_text(f"{digest}  {zp.name}\n")
print(json.dumps({"zip":str(zp),"sha256":digest},indent=2))
PY
}

self_test() {
  bash -n "$0"
  test -f "$CLEANER_DIR/install.sh"
  test -f "$CLEANER_DIR/frost_library_cleanerd.py"
  test -f "$CLEANER_DIR/package_evidence.py"
  if is_real_termux; then
    write_status "SELF_TEST_PASS_TERMUX" "repository solver and cleaner inputs present"
  else
    write_status "SELF_TEST_PASS_HOST_DEVICE_ACTION_REQUIRED" "physical execution requires Android/Termux"
  fi
}

run_device_cycle() {
  if ! is_real_termux; then
    self_test >/dev/null
    write_status "DEVICE_ACTION_REQUIRED_REAL_TERMUX" "run this solver inside the authorized Android Termux app"
    return 20
  fi
  if ! mkdir "$LOCK" 2>/dev/null; then
    write_status "ALREADY_RUNNING" "another physical-boundary cycle owns the lock"
    return 21
  fi
  trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

  local stamp run armed proof_rc
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  run="$RUN_HOME/$stamp"; mkdir -p "$run"
  exec > >(tee -a "$run/solver.stdout.log") 2> >(tee -a "$run/solver.stderr.log" >&2)

  ensure_dependencies
  if [ ! -e "$HOME/storage/downloads" ]; then termux-setup-storage || true; fi
  if [ -d "$HOME/storage/downloads" ]; then
    EVIDENCE_ROOT="$HOME/storage/downloads/FrostForgePhysicalBoundaryEvidence"
  else
    EVIDENCE_ROOT="$HOME/FrostForgePhysicalBoundaryEvidence"
  fi
  mkdir -p "$EVIDENCE_ROOT"
  capture_profile "$run/device_profile.json"

  if try_adb_reconnect; then
    echo '{"adb":"CONNECTED_OR_RECONNECTED"}' > "$run/adb_status.json"
  else
    echo '{"adb":"PAIRING_REQUIRED"}' > "$run/adb_status.json"
  fi

  bash "$CLEANER_DIR/install.sh" > "$run/cleaner_install.log" 2>&1 || true
  [ -f "$APP/config.json" ] && cp "$APP/config.json" "$run/cleaner_config_after_install.json" || true
  [ -f "$APP/qualification-result.json" ] && cp "$APP/qualification-result.json" "$run/qualification-result.json" || true

  armed="$(python - "$APP/config.json" <<'PY'
import json,sys
try: print("true" if json.load(open(sys.argv[1])).get("auto_delete") is True else "false")
except Exception: print("false")
PY
)"
  if [ "$armed" = "true" ]; then
    python - "$APP/config.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d["max_deletes_per_cycle"]=1
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n")
PY
    sv down "$SERVICE" >/dev/null 2>&1 || true
    set +e
    python "$APP/frost_library_cleanerd.py" once > "$run/first_physical_proof.json" 2> "$run/first_physical_proof.stderr"
    proof_rc=$?
    set -e
    printf '%s\n' "$proof_rc" > "$run/first_physical_proof.exit_code"
    "$APP/disarm.sh" > "$run/disarm.log" 2>&1 || true
  else
    echo '{"status":"QUALIFICATION_NOT_ARMED","reason":"ADB/UI qualification incomplete"}' > "$run/first_physical_proof.json"
  fi

  python "$APP/package_evidence.py" > "$run/cleaner_evidence_packager.json" 2> "$run/cleaner_evidence_packager.stderr" || true
  [ -f "$APP/config.json" ] && cp "$APP/config.json" "$run/cleaner_config_final.json" || true
  [ -f "$APP/state.json" ] && cp "$APP/state.json" "$run/cleaner_state_final.json" || true
  [ -f "$APP/archive-ledger.jsonl" ] && cp "$APP/archive-ledger.jsonl" "$run/archive-ledger.jsonl" || true

  local final
  final="$(python - "$run/first_physical_proof.json" <<'PY'
import json,sys
try: p=json.load(open(sys.argv[1]))
except Exception: p={}
if p.get("deleted"): print("PHYSICAL_CLEANER_PROOF_DELETE_VERIFIED_LOCALLY")
elif p.get("found") is not None and not p.get("errors"): print("PHYSICAL_CLEANER_INSTALLED_QUALIFIED_NO_DELETE_NEEDED")
else: print("DEVICE_ACTION_REQUIRED_ADB_OR_LIBRARY_UI")
PY
)"
  write_status "$final" "physical cycle completed; first proof ends disarmed pending review"
  cp "$STATE_HOME/status.json" "$run/final_status.json"
  package_evidence "$run"
  [ "$final" != "DEVICE_ACTION_REQUIRED_ADB_OR_LIBRARY_UI" ] || return 22
}

case "${1:---run}" in
  --self-test) self_test ;;
  --status) [ -f "$STATE_HOME/status.json" ] && cat "$STATE_HOME/status.json" || write_status "NEVER_RUN" "" ;;
  --run|--resume) run_device_cycle ;;
  *) echo "usage: $0 [--run|--resume|--self-test|--status]" >&2; exit 2 ;;
esac
