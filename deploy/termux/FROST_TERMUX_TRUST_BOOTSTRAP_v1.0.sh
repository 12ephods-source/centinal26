#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

MODE="${1:---doctor}"
ARG="${2:-}"
STATE_ROOT="${FROST_TERMUX_TRUST_ROOT:-$HOME/.local/state/frost-forge/termux-trust-bootstrap}"
TERMUX_PACKAGES_COMMIT='da8b07830fd2049bc4df6119befceb565732e36b'
TERMUX_AUTOBUILD_BLOB_SHA='c5ed76a1b9a1f2bc2e296bdd5ca50cf1f1f12706'
TERMUX_AUTOBUILD_FINGERPRINT='CC72CF8BA7DBFA0182877D045A897D96E57CF20C'
TERMUX_AUTOBUILD_KEY_ID='5A897D96E57CF20C'
TERMUX_AUTOBUILD_URL="https://raw.githubusercontent.com/termux/termux-packages/${TERMUX_PACKAGES_COMMIT}/packages/termux-keyring/termux-autobuilds.gpg"
SHARE_KEY="$PREFIX/share/termux-keyring/termux-autobuilds.gpg"
APT_KEY="$PREFIX/etc/apt/trusted.gpg.d/termux-autobuilds.gpg"

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha_file() { sha256sum "$1" | awk '{print $1}'; }
git_blob() { git hash-object "$1"; }
key_fingerprint() {
  gpg --batch --quiet --show-keys --with-colons "$1" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}'
}

require_termux() {
  case "${PREFIX:-}" in
    */com.termux/*) ;;
    *) echo "BLOCKED: this trust bootstrap must run inside Termux" >&2; return 10 ;;
  esac
  command -v getprop >/dev/null 2>&1 || {
    echo "BLOCKED: Android getprop is unavailable" >&2
    return 11
  }
  [ -n "$(getprop ro.build.version.release 2>/dev/null || true)" ] || {
    echo "BLOCKED: Android build properties are unavailable" >&2
    return 12
  }
  for tool in awk cp curl find git gpg install ln readlink sha256sum sort; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "BLOCKED: required local verification tool missing: $tool" >&2
      return 13
    }
  done
}

capture_state() {
  local out="$1" fingerprint="" blob=""
  mkdir -p "$out"
  if [ -f "$SHARE_KEY" ]; then
    fingerprint="$(key_fingerprint "$SHARE_KEY" || true)"
    blob="$(git_blob "$SHARE_KEY" 2>/dev/null || true)"
  fi
  {
    printf 'observed_at=%s\n' "$(now_iso)"
    printf 'prefix=%s\n' "$PREFIX"
    printf 'android_release=%s\n' "$(getprop ro.build.version.release 2>/dev/null || true)"
    printf 'official_termux_packages_commit=%s\n' "$TERMUX_PACKAGES_COMMIT"
    printf 'expected_git_blob_sha=%s\n' "$TERMUX_AUTOBUILD_BLOB_SHA"
    printf 'expected_fingerprint=%s\n' "$TERMUX_AUTOBUILD_FINGERPRINT"
    printf 'expected_key_id=%s\n' "$TERMUX_AUTOBUILD_KEY_ID"
    printf 'share_key_present=%s\n' "$([ -f "$SHARE_KEY" ] && echo yes || echo no)"
    printf 'apt_key_present=%s\n' "$([ -e "$APT_KEY" ] || [ -L "$APT_KEY" ] && echo yes || echo no)"
    printf 'share_key_git_blob_sha=%s\n' "$blob"
    printf 'share_key_fingerprint=%s\n' "$fingerprint"
    printf 'apt_key_symlink_target=%s\n' "$(readlink "$APT_KEY" 2>/dev/null || true)"
  } > "$out/summary.txt"
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

backup_existing() {
  local out="$1"
  mkdir -p "$out/backup"
  if [ -f "$SHARE_KEY" ]; then
    printf 'yes\n' > "$out/backup/share.present"
    cp -p "$SHARE_KEY" "$out/backup/share-termux-autobuilds.gpg"
  else
    printf 'no\n' > "$out/backup/share.present"
  fi
  if [ -e "$APT_KEY" ] || [ -L "$APT_KEY" ]; then
    printf 'yes\n' > "$out/backup/apt.present"
    cp -a "$APT_KEY" "$out/backup/apt-termux-autobuilds.gpg"
  else
    printf 'no\n' > "$out/backup/apt.present"
  fi
}

restore_backup() {
  local source_dir="$1" backup="$source_dir/backup"
  [ -d "$backup" ] || {
    echo "BLOCKED: trust backup not found under $source_dir" >&2
    return 50
  }
  rm -f "$SHARE_KEY" "$APT_KEY"
  if [ "$(cat "$backup/share.present" 2>/dev/null || echo no)" = yes ]; then
    mkdir -p "$(dirname "$SHARE_KEY")"
    cp -p "$backup/share-termux-autobuilds.gpg" "$SHARE_KEY"
  fi
  if [ "$(cat "$backup/apt.present" 2>/dev/null || echo no)" = yes ]; then
    mkdir -p "$(dirname "$APT_KEY")"
    cp -a "$backup/apt-termux-autobuilds.gpg" "$APT_KEY"
  fi
}

verify_payload() {
  local file="$1" actual_blob actual_fingerprint
  actual_blob="$(git_blob "$file")"
  actual_fingerprint="$(key_fingerprint "$file")"
  [ "$actual_blob" = "$TERMUX_AUTOBUILD_BLOB_SHA" ] || {
    echo "BLOCKED: key payload does not match pinned official Git blob" >&2
    echo "expected_blob=$TERMUX_AUTOBUILD_BLOB_SHA actual_blob=$actual_blob" >&2
    return 43
  }
  [ "$actual_fingerprint" = "$TERMUX_AUTOBUILD_FINGERPRINT" ] || {
    echo "BLOCKED: key fingerprint does not match pinned Termux autobuild identity" >&2
    echo "expected_fingerprint=$TERMUX_AUTOBUILD_FINGERPRINT actual_fingerprint=$actual_fingerprint" >&2
    return 44
  }
}

doctor() {
  require_termux
  local stamp out status=PASS
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/doctor-$stamp"
  capture_state "$out"
  if [ ! -f "$SHARE_KEY" ] || { [ ! -e "$APT_KEY" ] && [ ! -L "$APT_KEY" ]; }; then
    status=BLOCKED_TRUST_ANCHOR_MISSING
  elif ! verify_payload "$SHARE_KEY" > "$out/verify.stdout.txt" 2> "$out/verify.stderr.txt"; then
    status=BLOCKED_TRUST_ANCHOR_IDENTITY
  elif [ "$(readlink "$APT_KEY" 2>/dev/null || true)" != "$SHARE_KEY" ]; then
    status=BLOCKED_APT_TRUST_PATH
  fi
  printf 'status=%s\n' "$status" >> "$out/summary.txt"
  seal_dir "$out"
  cat "$out/summary.txt"
  printf 'doctor_dir=%s\n' "$out"
  [ "$status" = PASS ]
}

bootstrap() {
  require_termux
  [ "${FROST_ALLOW_TRUST_BOOTSTRAP:-0}" = "1" ] || {
    echo "BLOCKED: trust-root mutation requires FROST_ALLOW_TRUST_BOOTSTRAP=1" >&2
    exit 40
  }
  local stamp out downloaded rc=0
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/bootstrap-$stamp"
  capture_state "$out/before"
  backup_existing "$out"
  downloaded="$out/termux-autobuilds.gpg.download"

  curl -fL --proto '=https' --tlsv1.2 "$TERMUX_AUTOBUILD_URL" -o "$downloaded"
  sha_file "$downloaded" > "$out/downloaded.sha256"
  git_blob "$downloaded" > "$out/downloaded.git-blob-sha"
  key_fingerprint "$downloaded" > "$out/downloaded.fingerprint"
  verify_payload "$downloaded" > "$out/payload-verify.stdout.txt" 2> "$out/payload-verify.stderr.txt" || {
    rc=$?
    seal_dir "$out"
    exit "$rc"
  }

  mkdir -p "$(dirname "$SHARE_KEY")" "$(dirname "$APT_KEY")"
  install -m 600 "$downloaded" "$SHARE_KEY"
  ln -sfn "$SHARE_KEY" "$APT_KEY"

  if ! verify_payload "$SHARE_KEY" > "$out/install-verify.stdout.txt" 2> "$out/install-verify.stderr.txt" || \
     [ "$(readlink "$APT_KEY" 2>/dev/null || true)" != "$SHARE_KEY" ]; then
    rc=45
    restore_backup "$out" || true
    capture_state "$out/after-rollback" || true
    seal_dir "$out"
    echo "BLOCKED: installed trust anchor failed post-write verification; previous trust state restored" >&2
    exit "$rc"
  fi

  capture_state "$out/after"
  seal_dir "$out"
  printf 'FROST_TERMUX_TRUST_BOOTSTRAP_READY\n'
  printf 'bootstrap_dir=%s\n' "$out"
  printf 'rollback_snapshot=%s\n' "$out/backup"
  printf 'NEXT: run FROST_TERMUX_REPOSITORY_RECOVERY_v1.0.sh --repair; APT signature verification remains authoritative.\n'
}

rollback() {
  require_termux
  [ "${FROST_ALLOW_TRUST_BOOTSTRAP:-0}" = "1" ] || {
    echo "BLOCKED: trust-root rollback requires FROST_ALLOW_TRUST_BOOTSTRAP=1" >&2
    exit 40
  }
  [ -n "$ARG" ] || { echo "usage: $0 --rollback <bootstrap-dir>" >&2; exit 64; }
  local stamp out
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/rollback-$stamp"
  capture_state "$out/before"
  restore_backup "$ARG"
  capture_state "$out/after"
  seal_dir "$out"
  printf 'FROST_TERMUX_TRUST_ROLLBACK_COMPLETE\nrollback_dir=%s\n' "$out"
}

case "$MODE" in
  --doctor) doctor ;;
  --bootstrap) bootstrap ;;
  --rollback) rollback ;;
  *)
    echo "usage: $0 [--doctor|--bootstrap|--rollback <bootstrap-dir>]" >&2
    exit 64
    ;;
esac
