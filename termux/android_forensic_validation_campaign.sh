#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO_ROOT="${CENTINAL26_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
GATE_ROOT="${AUTOMATION_INTELLIGENCE_GATE_ROOT:-$HOME/.automation_intelligence_gate}"
CAMPAIGN_ROOT="${CENTINAL26_CAMPAIGN_ROOT:-$HOME/.local/state/centinal26/android-forensic-campaigns}"
FINALIZER="$REPO_ROOT/termux/automation_project_finalizer.sh"
FROST_WORKSPACE="${FROST_CASE_WORKSPACE:-$HOME/FROST_CASE}"
FROST_SCAN_ROOT="${FROST_SCAN_ROOT:-$HOME/storage/downloads}"
MODE="${1:---doctor}"

mkdir -p "$CAMPAIGN_ROOT"
chmod 700 "$CAMPAIGN_ROOT" 2>/dev/null || true

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
boot_id() {
  if [ -r /proc/sys/kernel/random/boot_id ]; then
    cat /proc/sys/kernel/random/boot_id
  else
    awk '$1 == "btime" {print "btime:" $2}' /proc/stat 2>/dev/null || printf 'unknown\n'
  fi
}
sha_file() { sha256sum "$1" | awk '{print $1}'; }

require_termux() {
  case "${PREFIX:-}" in
    */com.termux/*) ;;
    *) echo "BLOCKED: must run inside the official Termux application environment" >&2; return 10 ;;
  esac
  command -v getprop >/dev/null 2>&1 || {
    echo "BLOCKED: Android getprop is unavailable" >&2
    return 11
  }
  [ -n "$(getprop ro.build.version.release 2>/dev/null || true)" ] || {
    echo "BLOCKED: Android build properties are unavailable" >&2
    return 12
  }
}

require_campaign_tools() {
  local missing=0 tool
  for tool in git python jq sha256sum find sort; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "BLOCKED: missing required command: $tool" >&2
      missing=1
    fi
  done
  [ "$missing" -eq 0 ] || return 13
  [ -x "$FINALIZER" ] || {
    echo "BLOCKED: missing Centinal26 finalizer: $FINALIZER" >&2
    return 14
  }
}

frost_bin() {
  if [ -n "${FROST_FORENSICS_BIN:-}" ] && [ -x "$FROST_FORENSICS_BIN" ]; then
    printf '%s\n' "$FROST_FORENSICS_BIN"
    return 0
  fi
  command -v frost-forensics 2>/dev/null || true
}

capture_apt_state() {
  local out="$1"
  mkdir -p "$out"
  {
    printf 'observed_at=%s\n' "$(now_iso)"
    printf 'prefix=%s\n' "${PREFIX:-}"
    printf 'termux_change_repo=%s\n' "$(command -v termux-change-repo 2>/dev/null || true)"
    printf 'pkg=%s\n' "$(command -v pkg 2>/dev/null || true)"
    printf 'apt=%s\n' "$(command -v apt 2>/dev/null || true)"
  } > "$out/environment.txt"

  if command -v termux-info >/dev/null 2>&1; then
    termux-info > "$out/termux-info.stdout.txt" 2> "$out/termux-info.stderr.txt" || true
  fi
  if command -v dpkg-query >/dev/null 2>&1; then
    dpkg-query -W -f='${Package}\t${Version}\n' \
      termux-keyring termux-tools apt gpgv python git jq coreutils \
      > "$out/packages.tsv" 2> "$out/packages.stderr.txt" || true
  fi

  : > "$out/apt-sources.txt"
  if [ -n "${PREFIX:-}" ]; then
    if [ -f "$PREFIX/etc/apt/sources.list" ]; then
      printf '# %s\n' "$PREFIX/etc/apt/sources.list" >> "$out/apt-sources.txt"
      cat "$PREFIX/etc/apt/sources.list" >> "$out/apt-sources.txt" || true
    fi
    if [ -d "$PREFIX/etc/apt/sources.list.d" ]; then
      local f
      for f in "$PREFIX"/etc/apt/sources.list.d/*.list; do
        [ -f "$f" ] || continue
        printf '\n# %s\n' "$f" >> "$out/apt-sources.txt"
        cat "$f" >> "$out/apt-sources.txt" || true
      done
    fi
  fi
}

record_step() {
  local run_dir="$1" name="$2" expected_rc="$3"
  shift 3
  local stdout="$run_dir/steps/${name}.stdout" stderr="$run_dir/steps/${name}.stderr"
  local started completed rc command_text out_sha err_sha
  mkdir -p "$run_dir/steps"
  started="$(now_iso)"
  printf -v command_text '%q ' "$@"
  if "$@" > "$stdout" 2> "$stderr"; then
    rc=0
  else
    rc=$?
  fi
  completed="$(now_iso)"
  out_sha="$(sha_file "$stdout")"
  err_sha="$(sha_file "$stderr")"
  jq -nc \
    --arg name "$name" \
    --arg started_at "$started" \
    --arg completed_at "$completed" \
    --arg command "$command_text" \
    --arg stdout "$stdout" \
    --arg stderr "$stderr" \
    --arg stdout_sha256 "$out_sha" \
    --arg stderr_sha256 "$err_sha" \
    --argjson expected_rc "$expected_rc" \
    --argjson rc "$rc" \
    '{name:$name,started_at:$started_at,completed_at:$completed_at,command:$command,expected_rc:$expected_rc,exit_code:$rc,pass:($rc==$expected_rc),stdout:$stdout,stderr:$stderr,stdout_sha256:$stdout_sha256,stderr_sha256:$stderr_sha256}' \
    >> "$run_dir/steps.jsonl"
  [ "$rc" -eq "$expected_rc" ]
}

seal_payload() {
  local run_dir="$1" manifest="$run_dir/PAYLOAD_SHA256SUMS.txt"
  : > "$manifest.tmp"
  while IFS= read -r -d '' f; do
    case "$f" in
      "$manifest"|"$manifest.tmp"|"$run_dir/campaign_receipt.json"|"$run_dir/campaign_receipt.json.sha256") continue ;;
    esac
    printf '%s  %s\n' "$(sha_file "$f")" "${f#"$run_dir/"}" >> "$manifest.tmp"
  done < <(find "$run_dir" -type f -print0 | sort -z)
  mv "$manifest.tmp" "$manifest"
}

write_receipt() {
  local run_dir="$1" phase="$2" repo_commit="$3" pre_boot="$4" post_boot="$5" forensic_package="$6" centinal_report="$7"
  seal_payload "$run_dir"
  local manifest_sha forensic_sha="" centinal_sha="" steps_sha
  manifest_sha="$(sha_file "$run_dir/PAYLOAD_SHA256SUMS.txt")"
  steps_sha="$(sha_file "$run_dir/steps.jsonl")"
  [ -n "$forensic_package" ] && [ -f "$forensic_package" ] && forensic_sha="$(sha_file "$forensic_package")"
  [ -n "$centinal_report" ] && [ -f "$centinal_report" ] && centinal_sha="$(sha_file "$centinal_report")"
  jq -n \
    --arg schema "centinal26.android_forensic_validation_campaign/v1" \
    --arg phase "$phase" \
    --arg observed_at "$(now_iso)" \
    --arg repo_path "$REPO_ROOT" \
    --arg repo_commit "$repo_commit" \
    --arg pre_boot_id "$pre_boot" \
    --arg post_boot_id "$post_boot" \
    --arg frost_workspace "$FROST_WORKSPACE" \
    --arg frost_package "$forensic_package" \
    --arg frost_package_sha256 "$forensic_sha" \
    --arg centinal_report "$centinal_report" \
    --arg centinal_report_sha256 "$centinal_sha" \
    --arg payload_manifest "$run_dir/PAYLOAD_SHA256SUMS.txt" \
    --arg payload_manifest_sha256 "$manifest_sha" \
    --arg steps_sha256 "$steps_sha" \
    '{schema:$schema,phase:$phase,observed_at:$observed_at,repository:{path:$repo_path,commit:$repo_commit},boot_epoch:{pre:$pre_boot_id,post:$post_boot_id},forensics:{workspace:$frost_workspace,package:$frost_package,package_sha256:$frost_package_sha256},centinal26:{report:$centinal_report,report_sha256:$centinal_report_sha256},evidence:{payload_manifest:$payload_manifest,payload_manifest_sha256:$payload_manifest_sha256,steps_jsonl_sha256:$steps_sha256},promotion_authority:false}' \
    > "$run_dir/campaign_receipt.json.tmp"
  mv "$run_dir/campaign_receipt.json.tmp" "$run_dir/campaign_receipt.json"
  printf '%s  campaign_receipt.json\n' "$(sha_file "$run_dir/campaign_receipt.json")" > "$run_dir/campaign_receipt.json.sha256"
}

latest_case_package() {
  python - "$FROST_WORKSPACE" <<'PYLATEST'
from pathlib import Path
import sys
root = Path(sys.argv[1]).expanduser()
files = [p for p in root.rglob("*.zip") if p.is_file()] if root.exists() else []
if files:
    print(max(files, key=lambda p: (p.stat().st_mtime_ns, str(p))))
PYLATEST
}

doctor() {
  require_termux
  local stamp out fb status=PASS
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$CAMPAIGN_ROOT/doctor-$stamp"
  mkdir -p "$out"
  capture_apt_state "$out/package_state"
  if grep -Eqi '(^|[/:])termux\.net([/[:space:]]|$)|dl\.bintray\.com|science-packages|game-packages' "$out/package_state/apt-sources.txt"; then
    printf 'repository_warning=DEPRECATED_OR_LEGACY_SOURCE_DETECTED\n' > "$out/repository_warning.txt"
  fi
  {
    printf 'repo_root=%s\n' "$REPO_ROOT"
    printf 'repo_commit=%s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
    printf 'boot_id=%s\n' "$(boot_id)"
    printf 'finalizer=%s\n' "$FINALIZER"
  } > "$out/campaign_state.txt"

  if ! require_campaign_tools; then status=BLOCKED; fi
  fb="$(frost_bin)"
  if [ -z "$fb" ]; then
    echo "BLOCKED: frost-forensics is not installed or FROST_FORENSICS_BIN is not executable" >&2
    status=BLOCKED
  fi
  printf 'frost_forensics_bin=%s\nstatus=%s\n' "$fb" "$status" >> "$out/campaign_state.txt"
  (cd "$out" && sha256sum package_state/* campaign_state.txt 2>/dev/null | sort > SHA256SUMS.txt) || true
  printf 'doctor_status=%s\ndoctor_dir=%s\n' "$status" "$out"
  [ "$status" = PASS ]
}

repair_packages() {
  require_termux
  [ "${CENTINAL26_ALLOW_PACKAGE_REPAIR:-0}" = "1" ] || {
    echo "BLOCKED: package mutation requires CENTINAL26_ALLOW_PACKAGE_REPAIR=1" >&2
    exit 40
  }
  command -v pkg >/dev/null 2>&1 || { echo "BLOCKED: pkg command missing" >&2; exit 41; }
  local stamp out rc
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$CAMPAIGN_ROOT/package-repair-$stamp"
  mkdir -p "$out"
  capture_apt_state "$out/before"

  set +e
  pkg update -y > "$out/pkg-update.stdout.txt" 2> "$out/pkg-update.stderr.txt"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    capture_apt_state "$out/after-failure"
    (cd "$out" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt) || true
    echo "BLOCKED: authenticated pkg update failed (rc=$rc). No signature bypass was attempted." >&2
    echo "Use termux-change-repo to select a current Termux mirror, then rerun this mode." >&2
    exit "$rc"
  fi

  set +e
  pkg install -y termux-keyring termux-tools python git jq coreutils \
    > "$out/pkg-install.stdout.txt" 2> "$out/pkg-install.stderr.txt"
  rc=$?
  set -e
  capture_apt_state "$out/after"
  (cd "$out" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt) || true
  if [ "$rc" -ne 0 ]; then
    echo "BLOCKED: authenticated package installation failed (rc=$rc)." >&2
    exit "$rc"
  fi
  printf 'PACKAGE_REPAIR_PASS\nrepair_dir=%s\n' "$out"
}

pre_reboot() {
  require_termux
  require_campaign_tools
  local fb repo_commit run_id run_dir pre_boot forensic_package finalizer_rc
  fb="$(frost_bin)"
  [ -n "$fb" ] || {
    echo "BLOCKED: install Frost Forensics v3.1.0 first; no Centinal26 mutation has been started" >&2
    exit 42
  }
  repo_commit="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  pre_boot="$(boot_id)"
  run_id="$(date -u +%Y%m%dT%H%M%SZ)-${repo_commit:0:12}"
  run_dir="$CAMPAIGN_ROOT/$run_id"
  [ ! -e "$run_dir" ] || { echo "BLOCKED: campaign run already exists: $run_dir" >&2; exit 43; }
  mkdir -p "$run_dir"
  printf '%s\n' "$run_id" > "$CAMPAIGN_ROOT/active"
  capture_apt_state "$run_dir/package_state_pre"
  printf '%s\n' "$pre_boot" > "$run_dir/pre_boot_id"
  printf '%s\n' "$repo_commit" > "$run_dir/repo_commit"

  # Evidence acquisition intentionally precedes Centinal26 venv/bootstrap/boot mutations.
  record_step "$run_dir" frost_doctor 0 "$fb" --workspace "$FROST_WORKSPACE" doctor
  record_step "$run_dir" frost_android_live_pre 0 "$fb" --workspace "$FROST_WORKSPACE" acquire android-live
  record_step "$run_dir" frost_audit_pre 0 "$fb" --workspace "$FROST_WORKSPACE" audit
  record_step "$run_dir" frost_resolve_pre 0 "$fb" --workspace "$FROST_WORKSPACE" resolve
  record_step "$run_dir" frost_package_pre 0 "$fb" --workspace "$FROST_WORKSPACE" package-case
  forensic_package="$(latest_case_package)"
  [ -n "$forensic_package" ] && [ -f "$forensic_package" ] || {
    echo "FAIL: Frost Forensics did not produce a verifiable case package" >&2
    exit 44
  }
  record_step "$run_dir" frost_verify_package_pre 0 "$fb" --workspace "$FROST_WORKSPACE" verify-package "$forensic_package"

  # Existing Centinal26 physical gate is reused rather than duplicated.
  set +e
  record_step "$run_dir" centinal26_project_pre_reboot 20 env \
    CENTINAL26_REPO_ROOT="$REPO_ROOT" \
    AUTOMATION_INTELLIGENCE_GATE_ROOT="$GATE_ROOT" \
    "$FINALIZER" --pre-reboot
  finalizer_rc=$?
  set -e
  [ "$finalizer_rc" -eq 0 ] || {
    write_receipt "$run_dir" PRE_REBOOT_BLOCKED "$repo_commit" "$pre_boot" "" "$forensic_package" "$GATE_ROOT/project_pre_reboot.json"
    echo "FAIL: Centinal26 physical pre-reboot gate did not reach AWAITING_REBOOT" >&2
    exit 45
  }

  capture_apt_state "$run_dir/package_state_after_centinal"
  write_receipt "$run_dir" AWAITING_MANUAL_REBOOT "$repo_commit" "$pre_boot" "" "$forensic_package" "$GATE_ROOT/project_pre_reboot.json"
  cat "$run_dir/campaign_receipt.json"
  echo "NEXT: perform one normal Android reboot, then run this script with --post-reboot" >&2
  exit 20
}

post_reboot() {
  require_termux
  require_campaign_tools
  local fb run_id run_dir repo_commit pre_boot post_boot forensic_package final_report phase
  fb="$(frost_bin)"
  [ -n "$fb" ] || { echo "BLOCKED: frost-forensics is unavailable" >&2; exit 50; }
  [ -f "$CAMPAIGN_ROOT/active" ] || { echo "BLOCKED: no active campaign" >&2; exit 51; }
  run_id="$(cat "$CAMPAIGN_ROOT/active")"
  run_dir="$CAMPAIGN_ROOT/$run_id"
  [ -d "$run_dir" ] || { echo "BLOCKED: active campaign directory missing" >&2; exit 52; }
  repo_commit="$(cat "$run_dir/repo_commit")"
  pre_boot="$(cat "$run_dir/pre_boot_id")"
  post_boot="$(boot_id)"
  [ "$post_boot" != "$pre_boot" ] || { echo "BLOCKED: a new boot epoch has not been observed" >&2; exit 53; }
  [ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$repo_commit" ] || {
    echo "BLOCKED: repository HEAD changed across reboot; campaign identity is no longer stable" >&2
    exit 54
  }
  printf '%s\n' "$post_boot" > "$run_dir/post_boot_id"

  record_step "$run_dir" centinal26_project_post_reboot 0 env \
    CENTINAL26_REPO_ROOT="$REPO_ROOT" \
    AUTOMATION_INTELLIGENCE_GATE_ROOT="$GATE_ROOT" \
    "$FINALIZER" --post-reboot

  record_step "$run_dir" frost_android_live_post 0 "$fb" --workspace "$FROST_WORKSPACE" acquire android-live
  record_step "$run_dir" frost_audit_post 0 "$fb" --workspace "$FROST_WORKSPACE" audit
  record_step "$run_dir" frost_resolve_post 0 "$fb" --workspace "$FROST_WORKSPACE" resolve
  record_step "$run_dir" frost_package_post 0 "$fb" --workspace "$FROST_WORKSPACE" package-case
  forensic_package="$(latest_case_package)"
  [ -n "$forensic_package" ] && [ -f "$forensic_package" ] || { echo "FAIL: post-reboot case package missing" >&2; exit 55; }
  record_step "$run_dir" frost_verify_package_post 0 "$fb" --workspace "$FROST_WORKSPACE" verify-package "$forensic_package"

  final_report="$GATE_ROOT/project_final.json"
  [ -f "$final_report" ] || { echo "FAIL: Centinal26 final report missing" >&2; exit 56; }
  phase="$(jq -r '.phase // empty' "$final_report")"
  [ "$phase" = "READY_FOR_GA_PROMOTION" ] || {
    write_receipt "$run_dir" POST_REBOOT_BLOCKED "$repo_commit" "$pre_boot" "$post_boot" "$forensic_package" "$final_report"
    echo "FAIL: Centinal26 finalizer did not reach READY_FOR_GA_PROMOTION" >&2
    exit 57
  }

  capture_apt_state "$run_dir/package_state_post"
  write_receipt "$run_dir" CAMPAIGN_VALIDATED "$repo_commit" "$pre_boot" "$post_boot" "$forensic_package" "$final_report"
  cp "$run_dir/campaign_receipt.json" "$CAMPAIGN_ROOT/latest_validated_receipt.json"
  rm -f "$CAMPAIGN_ROOT/active"
  cat "$run_dir/campaign_receipt.json"
}

case "$MODE" in
  --doctor) doctor ;;
  --repair-packages) repair_packages ;;
  --pre-reboot) pre_reboot ;;
  --post-reboot) post_reboot ;;
  *)
    echo "usage: $0 [--doctor|--repair-packages|--pre-reboot|--post-reboot]" >&2
    exit 64
    ;;
esac
