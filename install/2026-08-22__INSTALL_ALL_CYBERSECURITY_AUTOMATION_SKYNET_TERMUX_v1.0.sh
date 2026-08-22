#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

OPENING='Yes, I will automate everything you requested in order to efficiently and successfully complete your requests, projects, and goals.'
CLOSING='Would you like to continue automatically using all tools, apps, and programs without asking again for as long as possible?'
printf '%s\n' "$OPENING"

REPO="${CENTINAL26_ROOT:-$HOME/centinal26}"
CYBER="${FROST_CYBERSECURITY_ROOT:-$HOME/Frost_Sentinel_Cybersecurity}"
STATE="${FROST_ALL_STATE:-$HOME/.frost_all}"
TEST_MODE="${FROST_INSTALL_TEST_MODE:-0}"
mkdir -p "$STATE" "$HOME/.termux/boot" "$HOME/.local/bin"
LOG="$STATE/install.log"
exec > >(tee -a "$LOG") 2>&1

say() { printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

if [[ "$TEST_MODE" != 1 ]]; then
  command -v pkg >/dev/null 2>&1 || fail 'Run this installer inside Termux.'
  say 'Installing required Termux packages'
  pkg update -y || true
  pkg install -y git python coreutils procps termux-api || pkg install -y git python coreutils procps
fi

command -v git >/dev/null 2>&1 || fail 'git is required'
command -v python >/dev/null 2>&1 || fail 'python is required'

sync_repo() {
  local repo="$1"
  if [[ ! -d "$repo/.git" ]]; then
    [[ "$TEST_MODE" == 1 ]] && fail "test mode requires an existing fixture repo: $repo"
    say 'Cloning canonical Centinal26 repository'
    git clone --branch main --single-branch https://github.com/12ephods-source/centinal26.git "$repo"
    return
  fi
  local dirty head remote base
  dirty="$(git -C "$repo" status --porcelain)"
  [[ -z "$dirty" ]] || fail "Centinal26 worktree is dirty; refusing to overwrite local work: $repo"
  say 'Fast-forwarding canonical Centinal26 repository'
  git -C "$repo" fetch --prune origin main
  head="$(git -C "$repo" rev-parse HEAD)"
  remote="$(git -C "$repo" rev-parse origin/main)"
  [[ "$head" == "$remote" ]] && return
  base="$(git -C "$repo" merge-base "$head" "$remote")"
  [[ "$base" == "$head" ]] || fail 'Centinal26 is locally ahead or diverged; refusing destructive update.'
  git -C "$repo" merge --ff-only origin/main
}

sync_repo "$REPO"

PAIR="$REPO/integrations/cybersecurity_automation/2026-08-22__FROST_CYBERSECURITY_AUTOMATION_PAIR_ONE_PASTE_v1.1.sh"
SKY="$REPO/skynet/v0.1/install_termux.sh"
[[ -f "$PAIR" ]] || fail "paired updater installer missing: $PAIR"
[[ -f "$SKY" ]] || fail "SKY NET installer missing: $SKY"

say 'Installing Cybersecurity + Automation paired runtime'
export FROST_AUTOMATION_ROOT="$REPO"
export FROST_CYBERSECURITY_ROOT="$CYBER"
export FROST_AUTOMATION_BRANCH=main
export FROST_CYBERSECURITY_BRANCH=main
export FROST_PAIR_STATE="${FROST_PAIR_STATE:-$HOME/.frost_project_pair}"
export FROST_SKIP_CLONE=1
export FROST_NO_DAEMON="${FROST_NO_DAEMON:-0}"
if [[ "$TEST_MODE" == 1 ]]; then
  FROST_NO_DAEMON=1 bash "$PAIR"
else
  bash "$PAIR"
fi

say 'Installing SKY NET bounded coordination worker'
export SKYNET_NO_DAEMON="${SKYNET_NO_DAEMON:-0}"
if [[ "$TEST_MODE" == 1 ]]; then
  SKYNET_NO_DAEMON=1 bash "$SKY"
else
  bash "$SKY"
fi

SKYBIN="$HOME/.local/bin/skynet"
[[ -x "$SKYBIN" ]] || fail 'SKY NET executable was not installed'

say 'Normalizing SKY NET project paths'
python - "$HOME/.skynet/config.json" "$REPO" "$CYBER" <<'PY'
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
repo = str(Path(sys.argv[2]).expanduser().resolve())
cyber = str(Path(sys.argv[3]).expanduser().resolve())
config = json.loads(cfg_path.read_text())
config.setdefault("project_paths", {})["automation"] = repo
config["project_paths"]["cybersecurity"] = cyber
cfg_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
PY

# Make SKY NET available on normal Termux PATH without requiring shell-profile edits.
if [[ -n "${PREFIX:-}" && -d "${PREFIX:-}/bin" && -w "${PREFIX:-}/bin" ]]; then
  ln -sfn "$SKYBIN" "$PREFIX/bin/skynet"
fi

STATUS="$HOME/.local/bin/frost-all-status"
cat > "$STATUS" <<'STATUS_EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u
printf '=== Cybersecurity + Automation + SKY NET ===\n'
printf 'time_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '\n-- paired updater --\n'
if command -v frost-pair-update >/dev/null 2>&1; then
  frost-pair-update --status-only || true
elif [[ -x "$PREFIX/bin/frost-pair-update" ]]; then
  "$PREFIX/bin/frost-pair-update" --status-only || true
else
  echo 'frost-pair-update: not found'
fi
printf '\n-- SKY NET --\n'
"$HOME/.local/bin/skynet" status || true
printf '\n-- SKY NET audit --\n'
"$HOME/.local/bin/skynet" verify-audit || true
printf '\n-- workers --\n'
pgrep -af 'update-loop.sh|/.skynet/worker.sh' || true
STATUS_EOF
chmod 700 "$STATUS"
if [[ -n "${PREFIX:-}" && -d "${PREFIX:-}/bin" && -w "${PREFIX:-}/bin" ]]; then
  ln -sfn "$STATUS" "$PREFIX/bin/frost-all-status"
fi

say 'Running bounded post-install verification'
"$SKYBIN" submit health >/dev/null
"$SKYBIN" work-once >/dev/null
"$SKYBIN" submit verify >/dev/null
"$SKYBIN" work-once >/dev/null || true
"$SKYBIN" verify-audit

PAIR_RC=0
if command -v frost-pair-update >/dev/null 2>&1; then
  frost-pair-update --status-only || PAIR_RC=$?
elif [[ -n "${PREFIX:-}" && -x "${PREFIX:-}/bin/frost-pair-update" ]]; then
  "$PREFIX/bin/frost-pair-update" --status-only || PAIR_RC=$?
else
  PAIR_RC=127
fi

python - "$STATE/install_receipt.json" "$REPO" "$CYBER" "$PAIR_RC" <<'PY'
import hashlib
import json
import sys
import time
from pathlib import Path

out = Path(sys.argv[1])
repo = Path(sys.argv[2])
cyber = Path(sys.argv[3])
pair_rc = int(sys.argv[4])
core = Path.home() / ".local/bin/skynet"
receipt = {
    "schema": 1,
    "installed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "automation_root": str(repo),
    "cybersecurity_root": str(cyber),
    "skynet_core": str(core),
    "skynet_sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
    "pair_status_rc": pair_rc,
    "physical_device_validation": "UNVERIFIED_UNLESS_THIS_RECEIPT_ORIGINATES_FROM_TERMUX_DEVICE",
}
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
Path(str(out) + ".sha256").write_text(
    hashlib.sha256(out.read_bytes()).hexdigest() + "  " + out.name + "\n"
)
PY

say 'Installation complete'
printf 'Automation:    %s\n' "$REPO"
printf 'Cybersecurity: %s\n' "$CYBER"
printf 'SKY NET:       %s\n' "$HOME/.skynet"
printf 'Receipt:       %s\n' "$STATE/install_receipt.json"
printf 'Status:        frost-all-status\n'
printf '%s\n' "$CLOSING"
