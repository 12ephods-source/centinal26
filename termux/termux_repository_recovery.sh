#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

MODE="${1:---doctor}"
ARG="${2:-}"
STATE_ROOT="${CENTINAL26_REPO_RECOVERY_ROOT:-$HOME/.local/state/centinal26/termux-repository-recovery}"
OFFICIAL_MAIN_SOURCE='deb https://packages.termux.dev/apt/termux-main stable main'
TERMUX_AUTOBUILD_KEY_ID='5A897D96E57CF20C'

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha_file() { sha256sum "$1" | awk '{print $1}'; }

require_termux() {
  case "${PREFIX:-}" in
    */com.termux/*) ;;
    *) echo "BLOCKED: this recovery tool must run inside Termux" >&2; return 10 ;;
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

source_files() {
  local f
  [ -f "$PREFIX/etc/apt/sources.list" ] && printf '%s\n' "$PREFIX/etc/apt/sources.list"
  for f in "$PREFIX"/etc/apt/sources.list.d/*.list; do
    [ -f "$f" ] && printf '%s\n' "$f"
  done
}

is_active_termux_main_line() {
  local line="$1"
  [[ "$line" =~ ^[[:space:]]*# ]] && return 1
  [[ "$line" =~ ^[[:space:]]*$ ]] && return 1
  [[ "$line" =~ termux-main|termux\.net|packages\.termux\.org|termux\.org/packages ]]
}

is_legacy_line() {
  local line="$1"
  [[ "$line" =~ termux\.net|packages\.termux\.org|termux\.org/packages|dl\.bintray\.com|science-packages|game-packages ]]
}

keyring_version() {
  if command -v dpkg-query >/dev/null 2>&1; then
    dpkg-query -W -f='${Version}\n' termux-keyring 2>/dev/null || true
  fi
}

keyring_anchor_present() {
  [ -e "$PREFIX/etc/apt/trusted.gpg.d/termux-autobuilds.gpg" ] || \
    [ -e "$PREFIX/share/termux-keyring/termux-autobuilds.gpg" ]
}

analyze_sources() {
  local file line main_count=0 legacy_count=0 canonical_count=0
  while IFS= read -r file; do
    while IFS= read -r line || [ -n "$line" ]; do
      if is_active_termux_main_line "$line"; then
        main_count=$((main_count + 1))
        [[ "$line" == *"https://packages.termux.dev/apt/termux-main"* ]] && canonical_count=$((canonical_count + 1))
      fi
      if [[ ! "$line" =~ ^[[:space:]]*# ]] && is_legacy_line "$line"; then
        legacy_count=$((legacy_count + 1))
      fi
    done < "$file"
  done < <(source_files)
  printf 'active_termux_main_sources=%s\n' "$main_count"
  printf 'canonical_primary_sources=%s\n' "$canonical_count"
  printf 'legacy_active_sources=%s\n' "$legacy_count"
}

capture_state() {
  local out="$1" file key
  mkdir -p "$out"
  {
    printf 'observed_at=%s\n' "$(now_iso)"
    printf 'prefix=%s\n' "$PREFIX"
    printf 'android_release=%s\n' "$(getprop ro.build.version.release 2>/dev/null || true)"
    printf 'pkg=%s\n' "$(command -v pkg 2>/dev/null || true)"
    printf 'apt=%s\n' "$(command -v apt 2>/dev/null || true)"
    printf 'termux_change_repo=%s\n' "$(command -v termux-change-repo 2>/dev/null || true)"
    printf 'termux_keyring_version=%s\n' "$(keyring_version)"
    if keyring_anchor_present; then
      printf 'termux_autobuild_key_anchor=PRESENT\n'
    else
      printf 'termux_autobuild_key_anchor=MISSING\n'
    fi
    printf 'expected_missing_key_id=%s\n' "$TERMUX_AUTOBUILD_KEY_ID"
    analyze_sources
  } > "$out/summary.txt"

  : > "$out/apt-sources.txt"
  while IFS= read -r file; do
    printf '# %s\n' "$file" >> "$out/apt-sources.txt"
    cat "$file" >> "$out/apt-sources.txt" || true
    printf '\n' >> "$out/apt-sources.txt"
  done < <(source_files)

  if command -v termux-info >/dev/null 2>&1; then
    termux-info > "$out/termux-info.stdout.txt" 2> "$out/termux-info.stderr.txt" || true
  fi

  : > "$out/keyring-files.tsv"
  for file in "$PREFIX"/etc/apt/trusted.gpg.d/* "$PREFIX"/share/termux-keyring/*; do
    [ -e "$file" ] || continue
    key=""
    [ -f "$file" ] && command -v sha256sum >/dev/null 2>&1 && key="$(sha_file "$file")"
    printf '%s\t%s\t%s\n' "$file" "$(readlink "$file" 2>/dev/null || true)" "$key" >> "$out/keyring-files.tsv"
  done
}

seal_dir() {
  local out="$1" f manifest="$out/SHA256SUMS.txt"
  command -v sha256sum >/dev/null 2>&1 || return 0
  : > "$manifest.tmp"
  if command -v find >/dev/null 2>&1 && command -v sort >/dev/null 2>&1; then
    while IFS= read -r -d '' f; do
      case "$f" in "$manifest"|"$manifest.tmp") continue ;; esac
      printf '%s  %s\n' "$(sha_file "$f")" "${f#"$out/"}" >> "$manifest.tmp"
    done < <(find "$out" -type f -print0 | sort -z)
  fi
  mv "$manifest.tmp" "$manifest"
}

backup_sources() {
  local out="$1"
  mkdir -p "$out/source-backup/etc/apt"
  if [ -f "$PREFIX/etc/apt/sources.list" ]; then
    cp -p "$PREFIX/etc/apt/sources.list" "$out/source-backup/etc/apt/sources.list"
  fi
  if [ -d "$PREFIX/etc/apt/sources.list.d" ]; then
    cp -a "$PREFIX/etc/apt/sources.list.d" "$out/source-backup/etc/apt/"
  fi
}

normalize_one_file() {
  local file="$1" tmp="$file.centinal26.tmp" line
  : > "$tmp"
  while IFS= read -r line || [ -n "$line" ]; do
    if is_active_termux_main_line "$line"; then
      printf '# CENTINAL26_DISABLED_MAIN_SOURCE %s\n' "$line" >> "$tmp"
    else
      printf '%s\n' "$line" >> "$tmp"
    fi
  done < "$file"
  mv "$tmp" "$file"
}

normalize_main_sources() {
  local file main_file="$PREFIX/etc/apt/sources.list"
  mkdir -p "$PREFIX/etc/apt/sources.list.d"
  while IFS= read -r file; do
    normalize_one_file "$file"
  done < <(source_files)
  printf '%s\n' "$OFFICIAL_MAIN_SOURCE" >> "$main_file"
}

restore_sources() {
  local repair_dir="$1" backup="$repair_dir/source-backup/etc/apt"
  [ -d "$backup" ] || {
    echo "BLOCKED: source backup not found under $repair_dir" >&2
    exit 50
  }
  mkdir -p "$PREFIX/etc/apt"
  rm -f "$PREFIX/etc/apt/sources.list"
  rm -rf "$PREFIX/etc/apt/sources.list.d"
  [ -f "$backup/sources.list" ] && cp -p "$backup/sources.list" "$PREFIX/etc/apt/sources.list"
  [ -d "$backup/sources.list.d" ] && cp -a "$backup/sources.list.d" "$PREFIX/etc/apt/"
}

doctor() {
  require_termux
  local stamp out main_count legacy_count canonical_count status=PASS
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/doctor-$stamp"
  capture_state "$out"
  main_count="$(awk -F= '/^active_termux_main_sources=/{print $2}' "$out/summary.txt")"
  canonical_count="$(awk -F= '/^canonical_primary_sources=/{print $2}' "$out/summary.txt")"
  legacy_count="$(awk -F= '/^legacy_active_sources=/{print $2}' "$out/summary.txt")"
  [ "$main_count" -eq 1 ] || status=BLOCKED
  [ "$canonical_count" -eq 1 ] || status=BLOCKED
  [ "$legacy_count" -eq 0 ] || status=BLOCKED
  keyring_anchor_present || status=BLOCKED
  [ -n "$(keyring_version)" ] || status=BLOCKED
  printf 'status=%s\n' "$status" >> "$out/summary.txt"
  seal_dir "$out"
  cat "$out/summary.txt"
  printf 'doctor_dir=%s\n' "$out"
  [ "$status" = PASS ]
}

repair() {
  require_termux
  [ "${CENTINAL26_ALLOW_PACKAGE_REPAIR:-0}" = "1" ] || {
    echo "BLOCKED: repository mutation requires CENTINAL26_ALLOW_PACKAGE_REPAIR=1" >&2
    exit 40
  }
  command -v pkg >/dev/null 2>&1 || { echo "BLOCKED: pkg is unavailable" >&2; exit 41; }
  local stamp out rc
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/repair-$stamp"
  capture_state "$out/before"
  backup_sources "$out"
  normalize_main_sources
  capture_state "$out/normalized"

  set +e
  pkg update -y > "$out/pkg-update.stdout.txt" 2> "$out/pkg-update.stderr.txt"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    capture_state "$out/after-failure"
    seal_dir "$out"
    if grep -Eq "NO_PUBKEY[[:space:]]+$TERMUX_AUTOBUILD_KEY_ID" "$out/pkg-update.stderr.txt"; then
      echo "BLOCKED: Termux repository signature key $TERMUX_AUTOBUILD_KEY_ID is unavailable to apt." >&2
      echo "This is a trust-anchor failure, not a mirror-selection failure; no key was imported and no signature check was bypassed." >&2
      echo "Rollback snapshot: $out/source-backup" >&2
      exit 42
    fi
    echo "BLOCKED: authenticated pkg update failed (rc=$rc). No signature bypass was attempted." >&2
    echo "Rollback snapshot: $out/source-backup" >&2
    exit "$rc"
  fi

  set +e
  pkg install -y termux-keyring termux-tools > "$out/pkg-install.stdout.txt" 2> "$out/pkg-install.stderr.txt"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    capture_state "$out/after-install-failure"
    seal_dir "$out"
    echo "BLOCKED: authenticated termux-keyring/termux-tools refresh failed (rc=$rc)." >&2
    echo "Rollback snapshot: $out/source-backup" >&2
    exit "$rc"
  fi

  set +e
  pkg update -y > "$out/pkg-update-verify.stdout.txt" 2> "$out/pkg-update-verify.stderr.txt"
  rc=$?
  set -e
  capture_state "$out/after"
  seal_dir "$out"
  [ "$rc" -eq 0 ] || {
    echo "BLOCKED: post-refresh authenticated pkg update failed (rc=$rc)." >&2
    exit "$rc"
  }
  keyring_anchor_present || { echo "BLOCKED: termux-autobuilds key anchor is still missing after keyring refresh" >&2; exit 43; }
  printf 'TERMUX_REPOSITORY_RECOVERY_PASS\nrepair_dir=%s\nrollback_snapshot=%s\n' "$out" "$out/source-backup"
}

rollback() {
  require_termux
  [ "${CENTINAL26_ALLOW_PACKAGE_REPAIR:-0}" = "1" ] || {
    echo "BLOCKED: repository rollback requires CENTINAL26_ALLOW_PACKAGE_REPAIR=1" >&2
    exit 40
  }
  [ -n "$ARG" ] || { echo "usage: $0 --rollback <repair-dir>" >&2; exit 64; }
  local stamp out
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/rollback-$stamp"
  capture_state "$out/before"
  restore_sources "$ARG"
  capture_state "$out/after"
  seal_dir "$out"
  printf 'TERMUX_REPOSITORY_ROLLBACK_COMPLETE\nrollback_dir=%s\n' "$out"
}

case "$MODE" in
  --doctor) doctor ;;
  --repair) repair ;;
  --rollback) rollback ;;
  *)
    echo "usage: $0 [--doctor|--repair|--rollback <repair-dir>]" >&2
    exit 64
    ;;
esac
