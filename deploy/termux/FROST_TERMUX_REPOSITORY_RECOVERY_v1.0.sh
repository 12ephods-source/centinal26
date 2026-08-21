#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

MODE="${1:---doctor}"
ARG="${2:-}"
STATE_ROOT="${FROST_TERMUX_REPO_RECOVERY_ROOT:-$HOME/.local/state/frost-forge/termux-repository-recovery}"
OFFICIAL_MAIN_SOURCE='deb https://packages-cf.termux.dev/apt/termux-main/ stable main'
OFFICIAL_MAIN_ALT='https://packages.termux.dev/apt/termux-main/'
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
  for tool in awk find sha256sum sort; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "BLOCKED: required local verification tool missing: $tool" >&2
      return 13
    }
  done
}

source_files() {
  local file
  [ -f "$PREFIX/etc/apt/sources.list" ] && printf '%s\n' "$PREFIX/etc/apt/sources.list"
  for file in "$PREFIX"/etc/apt/sources.list.d/*.list; do
    [ -f "$file" ] && printf '%s\n' "$file"
  done
}

active_line() {
  local line="$1"
  [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ ! "$line" =~ ^[[:space:]]*$ ]]
}

is_termux_main_line() {
  local line="$1"
  active_line "$line" || return 1
  [[ "$line" =~ ^[[:space:]]*deb(-src)?[[:space:]] ]] || return 1
  if [[ "$line" == *"/apt/termux-main"* ]]; then
    return 0
  fi
  if [[ "$line" =~ termux\.net|packages\.termux\.org|termux\.org/packages|dl\.bintray\.com ]] && \
     [[ "$line" != *"termux-root"* ]] && [[ "$line" != *"termux-x11"* ]] && \
     [[ "$line" =~ [[:space:]]main([[:space:]]|$) ]]; then
    return 0
  fi
  return 1
}

is_current_official_main_line() {
  local line="$1"
  is_termux_main_line "$line" || return 1
  [[ "$line" == *"https://packages-cf.termux.dev/apt/termux-main/"* ]] || \
    [[ "$line" == *"$OFFICIAL_MAIN_ALT"* ]] || \
    [[ "$line" == *"https://packages.termux.dev/apt/termux-main "* ]]
}

legacy_main_line() {
  local line="$1"
  is_termux_main_line "$line" || return 1
  is_current_official_main_line "$line" && return 1
  return 0
}

termux_main_deb822_files() {
  local file
  for file in "$PREFIX"/etc/apt/sources.list.d/*.sources; do
    [ -f "$file" ] || continue
    if grep -Eq 'termux-main|packages(-cf)?\.termux\.dev' "$file"; then
      printf '%s\n' "$file"
    fi
  done
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
  local file line main_count=0 official_count=0 legacy_count=0 deb822_count=0
  while IFS= read -r file; do
    while IFS= read -r line || [ -n "$line" ]; do
      if is_termux_main_line "$line"; then
        main_count=$((main_count + 1))
        if is_current_official_main_line "$line"; then
          official_count=$((official_count + 1))
        elif legacy_main_line "$line"; then
          legacy_count=$((legacy_count + 1))
        fi
      fi
    done < "$file"
  done < <(source_files)
  while IFS= read -r file; do
    [ -n "$file" ] && deb822_count=$((deb822_count + 1))
  done < <(termux_main_deb822_files)
  printf 'active_termux_main_sources=%s\n' "$main_count"
  printf 'official_termux_main_sources=%s\n' "$official_count"
  printf 'legacy_termux_main_sources=%s\n' "$legacy_count"
  printf 'unsupported_termux_main_deb822_sources=%s\n' "$deb822_count"
}

capture_state() {
  local out="$1" file digest=""
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
    printf 'known_missing_key_id=%s\n' "$TERMUX_AUTOBUILD_KEY_ID"
    printf 'preferred_main_source=%s\n' "$OFFICIAL_MAIN_SOURCE"
    analyze_sources
  } > "$out/summary.txt"

  : > "$out/apt-sources.txt"
  while IFS= read -r file; do
    printf '# %s\n' "$file" >> "$out/apt-sources.txt"
    cat "$file" >> "$out/apt-sources.txt" || true
    printf '\n' >> "$out/apt-sources.txt"
  done < <(source_files)

  : > "$out/deb822-termux-main-files.txt"
  termux_main_deb822_files > "$out/deb822-termux-main-files.txt" || true

  if command -v termux-info >/dev/null 2>&1; then
    termux-info > "$out/termux-info.stdout.txt" 2> "$out/termux-info.stderr.txt" || true
  fi

  : > "$out/keyring-files.tsv"
  for file in "$PREFIX"/etc/apt/trusted.gpg.d/* "$PREFIX"/share/termux-keyring/*; do
    [ -e "$file" ] || continue
    digest=""
    [ -f "$file" ] && digest="$(sha_file "$file")"
    printf '%s\t%s\t%s\n' "$file" "$(readlink "$file" 2>/dev/null || true)" "$digest" >> "$out/keyring-files.tsv"
  done
}

seal_dir() {
  local out="$1" file manifest="$out/SHA256SUMS.txt"
  : > "$manifest.tmp"
  while IFS= read -r -d '' file; do
    case "$file" in "$manifest"|"$manifest.tmp") continue ;; esac
    printf '%s  %s\n' "$(sha_file "$file")" "${file#"$out/"}" >> "$manifest.tmp"
  done < <(find "$out" -type f -print0 | sort -z)
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
  local file="$1" tmp="$file.frost-recovery.tmp" line
  : > "$tmp"
  while IFS= read -r line || [ -n "$line" ]; do
    if is_termux_main_line "$line"; then
      printf '# FROST_DISABLED_TERMUX_MAIN_SOURCE %s\n' "$line" >> "$tmp"
    else
      printf '%s\n' "$line" >> "$tmp"
    fi
  done < "$file"
  mv "$tmp" "$file"
}

normalize_main_sources() {
  local file main_file="$PREFIX/etc/apt/sources.list"
  if [ -n "$(termux_main_deb822_files)" ]; then
    echo "BLOCKED: deb822 Termux main source detected; this version will not rewrite .sources files" >&2
    return 46
  fi
  mkdir -p "$PREFIX/etc/apt/sources.list.d"
  while IFS= read -r file; do
    normalize_one_file "$file"
  done < <(source_files)
  touch "$main_file"
  printf '%s\n' "$OFFICIAL_MAIN_SOURCE" >> "$main_file"
}

restore_sources() {
  local repair_dir="$1" backup="$repair_dir/source-backup/etc/apt"
  [ -d "$backup" ] || {
    echo "BLOCKED: source backup not found under $repair_dir" >&2
    return 50
  }
  mkdir -p "$PREFIX/etc/apt"
  rm -f "$PREFIX/etc/apt/sources.list"
  rm -rf "$PREFIX/etc/apt/sources.list.d"
  [ -f "$backup/sources.list" ] && cp -p "$backup/sources.list" "$PREFIX/etc/apt/sources.list"
  [ -d "$backup/sources.list.d" ] && cp -a "$backup/sources.list.d" "$PREFIX/etc/apt/"
}

doctor() {
  require_termux
  local stamp out main_count official_count legacy_count deb822_count status=PASS
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/doctor-$stamp"
  capture_state "$out"
  main_count="$(awk -F= '/^active_termux_main_sources=/{print $2}' "$out/summary.txt")"
  official_count="$(awk -F= '/^official_termux_main_sources=/{print $2}' "$out/summary.txt")"
  legacy_count="$(awk -F= '/^legacy_termux_main_sources=/{print $2}' "$out/summary.txt")"
  deb822_count="$(awk -F= '/^unsupported_termux_main_deb822_sources=/{print $2}' "$out/summary.txt")"
  if [ "$main_count" -ne 1 ] || [ "$official_count" -ne 1 ] || [ "$legacy_count" -ne 0 ] || [ "$deb822_count" -ne 0 ]; then
    status=BLOCKED_SOURCE_CONFIGURATION
  elif ! keyring_anchor_present || [ -z "$(keyring_version)" ]; then
    status=BLOCKED_TRUST_ANCHOR
  fi
  printf 'status=%s\n' "$status" >> "$out/summary.txt"
  seal_dir "$out"
  cat "$out/summary.txt"
  printf 'doctor_dir=%s\n' "$out"
  [ "$status" = PASS ]
}

rollback_after_failure() {
  local out="$1"
  restore_sources "$out" || return 1
  capture_state "$out/after-source-rollback"
}

repair() {
  require_termux
  [ "${FROST_ALLOW_PACKAGE_REPAIR:-0}" = "1" ] || {
    echo "BLOCKED: repository mutation requires FROST_ALLOW_PACKAGE_REPAIR=1" >&2
    exit 40
  }
  command -v pkg >/dev/null 2>&1 || { echo "BLOCKED: pkg is unavailable" >&2; exit 41; }
  [ -z "$(termux_main_deb822_files)" ] || {
    echo "BLOCKED: deb822 Termux main source detected; preserve it and use termux-change-repo/manual review" >&2
    exit 46
  }

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
    capture_state "$out/after-update-failure"
    rollback_after_failure "$out" || true
    seal_dir "$out"
    if grep -Eq "NO_PUBKEY[[:space:]]+([A-F0-9]{16,40})?$TERMUX_AUTOBUILD_KEY_ID|NO_PUBKEY[[:space:]]+$TERMUX_AUTOBUILD_KEY_ID" "$out/pkg-update.stderr.txt"; then
      echo "BLOCKED: Termux repository signature key $TERMUX_AUTOBUILD_KEY_ID is unavailable to apt." >&2
      echo "Source configuration was restored. No key was imported and no signature check was bypassed." >&2
      echo "Trust-root recovery remains a separate verification boundary." >&2
      echo "evidence_dir=$out" >&2
      exit 42
    fi
    echo "BLOCKED: authenticated pkg update failed (rc=$rc); source configuration was restored." >&2
    echo "evidence_dir=$out" >&2
    exit "$rc"
  fi

  set +e
  pkg install -y termux-keyring termux-tools > "$out/pkg-install.stdout.txt" 2> "$out/pkg-install.stderr.txt"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    capture_state "$out/after-install-failure"
    rollback_after_failure "$out" || true
    seal_dir "$out"
    echo "BLOCKED: authenticated termux-keyring/termux-tools refresh failed (rc=$rc); source configuration was restored." >&2
    echo "evidence_dir=$out" >&2
    exit "$rc"
  fi

  set +e
  pkg update -y > "$out/pkg-update-verify.stdout.txt" 2> "$out/pkg-update-verify.stderr.txt"
  rc=$?
  set -e
  capture_state "$out/after"
  if [ "$rc" -ne 0 ]; then
    rollback_after_failure "$out" || true
    seal_dir "$out"
    echo "BLOCKED: post-refresh authenticated pkg update failed (rc=$rc); source configuration was restored." >&2
    echo "evidence_dir=$out" >&2
    exit "$rc"
  fi
  if ! keyring_anchor_present; then
    rollback_after_failure "$out" || true
    seal_dir "$out"
    echo "BLOCKED: Termux autobuild trust anchor is still missing; source configuration was restored." >&2
    echo "evidence_dir=$out" >&2
    exit 43
  fi

  seal_dir "$out"
  printf 'FROST_TERMUX_REPOSITORY_RECOVERY_PASS\n'
  printf 'repair_dir=%s\n' "$out"
  printf 'rollback_snapshot=%s\n' "$out/source-backup"
}

rollback() {
  require_termux
  [ "${FROST_ALLOW_PACKAGE_REPAIR:-0}" = "1" ] || {
    echo "BLOCKED: repository rollback requires FROST_ALLOW_PACKAGE_REPAIR=1" >&2
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
  printf 'FROST_TERMUX_REPOSITORY_ROLLBACK_COMPLETE\nrollback_dir=%s\n' "$out"
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
