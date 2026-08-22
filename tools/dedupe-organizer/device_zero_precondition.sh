#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO='https://github.com/12ephods-source/centinal26.git'
PIN='18941855035ec0bc463a40283e4893a724a7dae2'
ROOT="$HOME/dedupe-organizer"
STATE="$ROOT/state"
SRC="$ROOT/dedupe_organizer.py"
AUTOPILOT="$ROOT/device_autopilot.sh"
BOOT="$HOME/.termux/boot/dedupe-organizer.sh"

fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -n "${ANDROID_ROOT:-}${ANDROID_DATA:-}" ]] || fail 'Android environment not detected'
[[ "${PREFIX:-}" == *com.termux* ]] || fail 'Termux environment not detected'

command -v pkg >/dev/null 2>&1 || fail 'pkg unavailable'
# gh is a fixed dependency because device_autopilot.sh uses it for evidence PR
# submission when credentials are already available on the handset.
pkg install -y git python coreutils gh >/dev/null

if [[ ! -d "$HOME/storage/shared" ]]; then
  command -v termux-setup-storage >/dev/null 2>&1 || fail 'termux-setup-storage unavailable'
  termux-setup-storage || true
  for _ in $(seq 1 30); do
    [[ -d "$HOME/storage/shared" ]] && break
    sleep 1
  done
fi
[[ -d "$HOME/storage/shared" ]] || fail 'shared storage permission not yet granted'

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone --quiet --filter=blob:none "$REPO" "$TMP/repo"
git -C "$TMP/repo" checkout --quiet --detach "$PIN"
ACTUAL="$(git -C "$TMP/repo" rev-parse HEAD)"
[[ "$ACTUAL" == "$PIN" ]] || fail "source pin mismatch: $ACTUAL"

python "$TMP/repo/tools/dedupe-organizer/materialize.py" >/dev/null
GEN="$TMP/repo/tools/dedupe-organizer/generated/dedupe_organizer.py"
[[ -f "$GEN" ]] || fail 'materialized runtime missing'
RUNTIME_SHA="$(sha256sum "$GEN" | awk '{print $1}')"
[[ "$RUNTIME_SHA" == 'ac8560aa3cb077ca100f204604f2f98ea10bb03c9b7dc6b17c6c10e07d41404f' ]] || fail 'runtime SHA-256 mismatch'

mkdir -p "$ROOT" "$STATE" "$HOME/.termux/boot"
install -m 700 "$GEN" "$SRC"
install -m 700 "$TMP/repo/tools/dedupe-organizer/device_autopilot.sh" "$AUTOPILOT"

cat > "$PREFIX/bin/dedupe-organizer" <<WRAP
#!$PREFIX/bin/bash
exec python '$SRC' --root '$STATE' "\$@"
WRAP
chmod 700 "$PREFIX/bin/dedupe-organizer"

cat > "$BOOT" <<'BOOTEOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
mkdir -p "$HOME/dedupe-organizer/logs"
nohup dedupe-organizer daemon >>"$HOME/dedupe-organizer/logs/boot.log" 2>&1 &
BOOTEOF
chmod 700 "$BOOT"

python -m py_compile "$SRC"
dedupe-organizer self-test >/dev/null
dedupe-organizer doctor >/dev/null
bash -n "$AUTOPILOT"

printf 'INSTALL_VERIFIED pin=%s runtime_sha256=%s\n' "$PIN" "$RUNTIME_SHA"
exec "$AUTOPILOT"
