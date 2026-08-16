#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

MODE="${1:---doctor}"
STATE_ROOT="${CENTINAL26_TRUST_BOOTSTRAP_ROOT:-$HOME/.local/state/centinal26/termux-trust-bootstrap}"
TERMUX_PACKAGES_COMMIT='da8b07830fd2049bc4df6119befceb565732e36b'
TERMUX_AUTOBUILD_BLOB_SHA='c5ed76a1b9a1f2bc2e296bdd5ca50cf1f1f12706'
TERMUX_AUTOBUILD_KEY_ID='5A897D96E57CF20C'
TERMUX_AUTOBUILD_URL="https://raw.githubusercontent.com/termux/termux-packages/${TERMUX_PACKAGES_COMMIT}/packages/termux-keyring/termux-autobuilds.gpg"
SHARE_KEY="$PREFIX/share/termux-keyring/termux-autobuilds.gpg"
APT_KEY="$PREFIX/etc/apt/trusted.gpg.d/termux-autobuilds.gpg"

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sha_file() { sha256sum "$1" | awk '{print $1}'; }

require_termux() {
  case "${PREFIX:-}" in
    */com.termux/*) ;;
    *) echo "BLOCKED: this trust bootstrap must run inside Termux" >&2; return 10 ;;
  esac
  command -v getprop >/dev/null 2>&1 || {
    echo "BLOCKED: Android getprop is unavailable" >&2
    return 11
  }
}

capture_state() {
  local out="$1"
  mkdir -p "$out"
  {
    printf 'observed_at=%s\n' "$(now_iso)"
    printf 'prefix=%s\n' "$PREFIX"
    printf 'android_release=%s\n' "$(getprop ro.build.version.release 2>/dev/null || true)"
    printf 'termux_keyring_version=%s\n' "$(dpkg-query -W -f='${Version}' termux-keyring 2>/dev/null || true)"
    printf 'official_termux_packages_commit=%s\n' "$TERMUX_PACKAGES_COMMIT"
    printf 'expected_git_blob_sha=%s\n' "$TERMUX_AUTOBUILD_BLOB_SHA"
    printf 'expected_key_id=%s\n' "$TERMUX_AUTOBUILD_KEY_ID"
    printf 'share_key_present=%s\n' "$([ -f "$SHARE_KEY" ] && echo yes || echo no)"
    printf 'apt_key_present=%s\n' "$([ -e "$APT_KEY" ] && echo yes || echo no)"
    if [ -f "$SHARE_KEY" ] && command -v git >/dev/null 2>&1; then
      printf 'share_key_git_blob_sha=%s\n' "$(git hash-object "$SHARE_KEY" 2>/dev/null || true)"
    fi
  } > "$out/summary.txt"

  if command -v dpkg >/dev/null 2>&1; then
    dpkg -V termux-keyring > "$out/dpkg-verify.stdout.txt" 2> "$out/dpkg-verify.stderr.txt" || true
    dpkg -L termux-keyring > "$out/dpkg-files.txt" 2> "$out/dpkg-files.stderr.txt" || true
  fi
  : > "$out/keyring-listing.txt"
  ls -la "$PREFIX/share/termux-keyring" "$PREFIX/etc/apt/trusted.gpg.d" \
    > "$out/keyring-listing.txt" 2>&1 || true
}

seal_dir() {
  local out="$1" f manifest="$out/SHA256SUMS.txt"
  : > "$manifest.tmp"
  while IFS= read -r -d '' f; do
    case "$f" in "$manifest"|"$manifest.tmp") continue ;; esac
    printf '%s  %s\n' "$(sha_file "$f")" "${f#"$out/"}" >> "$manifest.tmp"
  done < <(find "$out" -type f -print0 | sort -z)
  mv "$manifest.tmp" "$manifest"
}

doctor() {
  require_termux
  local stamp out status=PASS
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/doctor-$stamp"
  capture_state "$out"
  [ -f "$SHARE_KEY" ] || status=BLOCKED
  [ -e "$APT_KEY" ] || status=BLOCKED
  if [ -f "$SHARE_KEY" ] && command -v git >/dev/null 2>&1; then
    [ "$(git hash-object "$SHARE_KEY")" = "$TERMUX_AUTOBUILD_BLOB_SHA" ] || status=BLOCKED
  fi
  printf 'status=%s\n' "$status" >> "$out/summary.txt"
  seal_dir "$out"
  cat "$out/summary.txt"
  printf 'doctor_dir=%s\n' "$out"
  [ "$status" = PASS ]
}

bootstrap() {
  require_termux
  [ "${CENTINAL26_ALLOW_TRUST_BOOTSTRAP:-0}" = "1" ] || {
    echo "BLOCKED: trust-root mutation requires CENTINAL26_ALLOW_TRUST_BOOTSTRAP=1" >&2
    exit 40
  }
  for tool in git sha256sum find sort; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "BLOCKED: required verification tool missing: $tool" >&2
      exit 41
    }
  done
  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    echo "BLOCKED: curl or wget is required" >&2
    exit 42
  fi

  local stamp out downloaded actual_blob
  mkdir -p "$STATE_ROOT"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$STATE_ROOT/bootstrap-$stamp"
  mkdir -p "$out/backup"
  capture_state "$out/before"

  [ -f "$SHARE_KEY" ] && cp -p "$SHARE_KEY" "$out/backup/share-termux-autobuilds.gpg" || true
  if [ -e "$APT_KEY" ] || [ -L "$APT_KEY" ]; then
    cp -a "$APT_KEY" "$out/backup/apt-termux-autobuilds.gpg" 2>/dev/null || true
    readlink "$APT_KEY" > "$out/backup/apt-termux-autobuilds.symlink-target" 2>/dev/null || true
  fi

  downloaded="$out/termux-autobuilds.gpg.download"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --proto '=https' --tlsv1.2 "$TERMUX_AUTOBUILD_URL" -o "$downloaded"
  else
    wget -O "$downloaded" "$TERMUX_AUTOBUILD_URL"
  fi

  actual_blob="$(git hash-object "$downloaded")"
  printf '%s\n' "$actual_blob" > "$out/downloaded.git-blob-sha"
  sha_file "$downloaded" > "$out/downloaded.sha256"
  [ "$actual_blob" = "$TERMUX_AUTOBUILD_BLOB_SHA" ] || {
    seal_dir "$out"
    echo "BLOCKED: downloaded key does not match the pinned official Termux Git blob" >&2
    echo "expected=$TERMUX_AUTOBUILD_BLOB_SHA actual=$actual_blob" >&2
    exit 43
  }

  mkdir -p "$PREFIX/share/termux-keyring" "$PREFIX/etc/apt/trusted.gpg.d"
  install -m 600 "$downloaded" "$SHARE_KEY"
  ln -sfn "$SHARE_KEY" "$APT_KEY"

  [ "$(git hash-object "$SHARE_KEY")" = "$TERMUX_AUTOBUILD_BLOB_SHA" ] || {
    echo "BLOCKED: installed key payload changed after installation" >&2
    exit 44
  }
  [ "$(git hash-object -L "$APT_KEY" 2>/dev/null || git hash-object "$APT_KEY")" = "$TERMUX_AUTOBUILD_BLOB_SHA" ] || {
    echo "BLOCKED: apt trust-path payload does not match the pinned key" >&2
    exit 45
  }

  capture_state "$out/after"
  seal_dir "$out"
  printf 'TERMUX_TRUST_BOOTSTRAP_READY\nbootstrap_dir=%s\n' "$out"
  printf 'NEXT: run the Centinal26 repository recovery --repair mode; APT signature verification remains authoritative.\n'
}

case "$MODE" in
  --doctor) doctor ;;
  --bootstrap) bootstrap ;;
  *)
    echo "usage: $0 [--doctor|--bootstrap]" >&2
    exit 64
    ;;
esac
