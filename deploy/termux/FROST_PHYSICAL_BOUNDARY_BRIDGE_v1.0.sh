#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

MODE="${1:-auto}"
MAX_CYCLES="${FROST_IMPROVEMENT_CYCLES:-3}"
REPO_URL="${FROST_REPO_URL:-https://github.com/12ephods-source/centinal26.git}"
WORKDIR="${FROST_BOUNDARY_WORKDIR:-$HOME/.local/share/frost-physical-boundary-bridge/repo}"
STATE_ROOT="${FROST_BOUNDARY_STATE_ROOT:-$HOME/.local/share/frost-physical-boundary-bridge}"
SOURCE_COMMIT="${FROST_BOUNDARY_SOURCE_COMMIT:-}"
DOWNLOAD_DIR="${FROST_BOUNDARY_DOWNLOAD_DIR:-$HOME/storage/downloads}"
mkdir -p "$STATE_ROOT"
LOG="$STATE_ROOT/bridge.log"
EVENTS="$STATE_ROOT/events.jsonl"

now(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
emit(){
  local event="$1"; shift || true
  local detail="${*:-}"
  printf '%s %s %s\n' "$(now)" "$event" "$detail" | tee -a "$LOG" >&2
  python - "$EVENTS" "$event" "$detail" <<'PY'
import json,pathlib,sys,time
p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True)
with p.open("a",encoding="utf-8") as f:
    f.write(json.dumps({"ts":time.time(),"event":sys.argv[2],"detail":sys.argv[3]},sort_keys=True)+"\n")
PY
}
is_termux(){ [ -n "${PREFIX:-}" ] && case "$PREFIX" in *com.termux*) return 0;; esac; return 1; }

write_receipt(){
  local path="$1" status="$2"
  python - "$path" "$status" "$SOURCE_COMMIT" "$EVENTS" <<'PY'
import hashlib,json,os,pathlib,platform,sys,time
out=pathlib.Path(sys.argv[1]); ev=pathlib.Path(sys.argv[4])
d={"schema":"frost.physical-boundary-bridge.receipt.v1","created_unix":time.time(),
"status":sys.argv[2],"source_commit":sys.argv[3] or None,
"runtime":{"platform":platform.platform(),"python":platform.python_version()},
"termux_prefix":os.environ.get("PREFIX"),
"events_sha256":hashlib.sha256(ev.read_bytes()).hexdigest() if ev.exists() else None,
"authority_boundary":"Local execution evidence only; external promotion requires independent controller verification."}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
}

host_preflight(){
  emit HOST_PREFLIGHT_START
  command -v bash >/dev/null
  command -v python >/dev/null || command -v python3 >/dev/null
  command -v sha256sum >/dev/null
  bash -n "$0"
  write_receipt "$STATE_ROOT/host_handoff_receipt.json" "HOST_READY_DEVICE_EXECUTION_REQUIRED"
  emit HOST_PREFLIGHT_PASS
  printf 'HOST_READY_DEVICE_EXECUTION_REQUIRED\n'
  printf 'Run this same script inside Android Termux. First-time Wireless Debugging pairing still requires Android authorization.\n'
}

ensure_deps(){
  emit TERMUX_DEPENDENCY_CHECK
  pkg update -y
  pkg install -y git python coreutils curl android-tools termux-services
}

sync_source(){
  emit SOURCE_SYNC_START
  mkdir -p "$(dirname "$WORKDIR")"
  if [ -d "$WORKDIR/.git" ]; then git -C "$WORKDIR" fetch --all --prune
  else git clone --filter=blob:none "$REPO_URL" "$WORKDIR"; fi
  if [ -n "$SOURCE_COMMIT" ]; then
    case "$SOURCE_COMMIT" in *[!0-9a-fA-F]*|'') emit SOURCE_INVALID; return 2;; esac
    [ "${#SOURCE_COMMIT}" -eq 40 ] || { emit SOURCE_INVALID_LENGTH; return 2; }
    git -C "$WORKDIR" fetch --depth 1 origin "$SOURCE_COMMIT"
    git -C "$WORKDIR" checkout --detach --force "$SOURCE_COMMIT"
  else
    git -C "$WORKDIR" fetch origin main
    git -C "$WORKDIR" checkout -B frost-boundary origin/main
  fi
  SOURCE_COMMIT="$(git -C "$WORKDIR" rev-parse HEAD)"
  export SOURCE_COMMIT
  emit SOURCE_SYNC_PASS "$SOURCE_COMMIT"
}

adb_reconnect(){
  if adb get-state 2>/dev/null | grep -qx device; then emit ADB_CONNECTED; return 0; fi
  emit ADB_RECONNECT_START
  local ep
  for ep in $(adb mdns services 2>/dev/null | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]+' | sort -u || true); do
    adb connect "$ep" >/dev/null 2>&1 || true
    if adb get-state 2>/dev/null | grep -qx device; then emit ADB_RECONNECT_PASS "$ep"; return 0; fi
  done
  emit ADB_PAIRING_REQUIRED "Android Wireless debugging must authorize first pairing once; then rerun this same script."
  return 3
}

install_components(){
  emit COMPONENT_INSTALL_START
  bash "$WORKDIR/deploy/termux/FROST_EVIDENCE_GATE_ONE_PASTE_v1.0.sh"
  bash "$WORKDIR/deploy/termux/library_cleaner/install.sh"
  "$HOME/.local/share/frost-library-cleaner/disarm.sh" >/dev/null 2>&1 || true
  emit COMPONENT_INSTALL_PASS "cleaner_disarmed_for_combined_cycle"
}

cycle(){
  local n="$1" failures=0 dry="$STATE_ROOT/cleaner_dry_run_cycle_${n}.json"
  emit IMPROVEMENT_CYCLE_START "$n"
  if "$HOME/bin/frost-evidence-gate" --state-root "$HOME/.local/share/frost-evidence-gate" doctor; then
    emit CYCLE_OBSERVATION evidence_gate_doctor_pass
  else emit CYCLE_OBSERVATION evidence_gate_doctor_failed; failures=$((failures+1)); fi

  local adb_rc=0
  adb_reconnect || adb_rc=$?
  if [ "$adb_rc" -eq 0 ]; then
    emit CYCLE_HYPOTHESIS local_adb_available
  elif [ "$adb_rc" -eq 3 ]; then
    "$HOME/.local/share/frost-library-cleaner/disarm.sh" >/dev/null 2>&1 || true
    emit CYCLE_HARD_BLOCKER "first_time_android_pairing_authorization_required"
    emit CYCLE_RESULT "DEVICE_ACTION_REQUIRED"
    return 3
  else
    emit CYCLE_HYPOTHESIS local_adb_transient_failure
    failures=$((failures+1))
  fi

  if python "$HOME/.local/share/frost-library-cleaner/frost_library_cleanerd.py" dry-run > "$dry"; then
    if python - "$dry" <<'PY'
import json,pathlib,sys
d=json.loads(pathlib.Path(sys.argv[1]).read_text())
raise SystemExit(0 if not d.get("errors") else 1)
PY
    then emit CYCLE_MEASUREMENT cleaner_dry_run_zero_errors
    else emit CYCLE_MEASUREMENT cleaner_dry_run_reported_errors; failures=$((failures+1)); fi
  else emit CYCLE_MEASUREMENT cleaner_dry_run_failed; failures=$((failures+1)); fi

  if [ "$failures" -eq 0 ]; then
    emit CYCLE_CRITIQUE "preconditions satisfied; reuse cleaner transaction rather than duplicate deletion logic"
    "$HOME/.local/share/frost-library-cleaner/qualify_and_arm.sh"
    emit CYCLE_RESULT PASS
    return 0
  fi
  "$HOME/.local/share/frost-library-cleaner/disarm.sh" >/dev/null 2>&1 || true
  emit CYCLE_CRITIQUE "fail closed; preserve evidence; retry only recoverable runtime conditions"
  emit CYCLE_RESULT "BLOCKED failures=$failures"
  return 1
}

package_evidence(){
  emit PACKAGE_START
  mkdir -p "$DOWNLOAD_DIR"
  python "$HOME/.local/share/frost-library-cleaner/package_evidence.py" || true
  local stamp out zip
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/bundle_$stamp"
  zip="$DOWNLOAD_DIR/FrostForgePhysicalBoundaryEvidence_$stamp.zip"
  mkdir -p "$out"
  cp "$LOG" "$EVENTS" "$out/" 2>/dev/null || true
  cp "$STATE_ROOT"/cleaner_dry_run_cycle_*.json "$out/" 2>/dev/null || true
  find "$HOME/.local/share/frost-evidence-gate" -maxdepth 3 -type f \
    \( -name '*.json' -o -name '*.sha256' -o -name '*.zip' \) -exec cp '{}' "$out/" \; 2>/dev/null || true
  write_receipt "$out/boundary_receipt.json" "DEVICE_EVIDENCE_CAPTURED_PENDING_INDEPENDENT_VERIFICATION"
  python - "$out" "$zip" <<'PY'
import pathlib,shutil,sys
r=pathlib.Path(sys.argv[1]); z=pathlib.Path(sys.argv[2])
shutil.make_archive(str(z.with_suffix("")),"zip",r.parent,r.name)
PY
  sha256sum "$zip" > "$zip.sha256"
  emit PACKAGE_PASS "$zip"
  printf '%s\n' "$zip"
}

device_run(){
  emit DEVICE_RUN_START
  ensure_deps
  sync_source
  install_components
  local i ok=0 cycle_rc=0
  for i in $(seq 1 "$MAX_CYCLES"); do
    cycle_rc=0
    cycle "$i" || cycle_rc=$?
    if [ "$cycle_rc" -eq 0 ]; then
      ok=1
      break
    fi
    if [ "$cycle_rc" -eq 3 ]; then
      emit IMPROVEMENT_DECISION "cycle=$i no_retry_external_android_authorization"
      break
    fi
    emit IMPROVEMENT_DECISION "cycle=$i retry_recoverable_only"
    sleep 2
  done
  if [ "$ok" -ne 1 ]; then
    package_evidence || true
    emit DEVICE_ACTION_REQUIRED "Resolve first-time ADB pairing or Library UI availability, then rerun same script."
    return 3
  fi
  emit COMMISSION_START
  if "$HOME/bin/frost-evidence-gate" --state-root "$HOME/.local/share/frost-evidence-gate" commission; then
    emit COMMISSION_PASS
  else
    emit COMMISSION_FAILED "preserving failure evidence"
    "$HOME/.local/share/frost-library-cleaner/disarm.sh" >/dev/null 2>&1 || true
    package_evidence || true
    return 4
  fi
  package_evidence
  emit DEVICE_RUN_PASS "pending independent controller verification"
}

case "$MODE" in
 auto) if is_termux; then device_run; else host_preflight; fi ;;
 host) host_preflight ;;
 device) is_termux || { emit WRONG_RUNTIME; exit 2; }; device_run ;;
 doctor) if is_termux; then adb_reconnect || true; else host_preflight; fi ;;
 *) printf 'Usage: %s [auto|host|device|doctor]\n' "$0" >&2; exit 2 ;;
esac
