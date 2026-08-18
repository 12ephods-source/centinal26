#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

REPO="https://github.com/12ephods-source/centinal26.git"
MAIN_SHA="7e2352adee2bc26ffc0cee15fee073a239bd34b3"
PERSIST_SHA="20dcbb6dae29eee302e2d566c2a4270d1b657971"
ROOT="${CENTINAL26_FLEET_ROOT:-$HOME/.local/share/centinal26-fleet-bootstrap}"
STATE="${CENTINAL26_HOME:-$HOME/.local/state/centinal26}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

say(){ printf '[frost-fleet] %s\n' "$*"; }
die(){ printf '[frost-fleet] ERROR: %s\n' "$*" >&2; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Run this inside Termux on any Android phone." ;;
esac

command -v pkg >/dev/null 2>&1 || die "Termux pkg is unavailable."

missing=()
need(){ command -v "$1" >/dev/null 2>&1 || missing+=("$2"); }
need git git
need python python
need sha256sum coreutils
need curl curl
need jq jq
need pgrep procps
need openssl openssl
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  missing+=("nodejs-lts")
fi

if ((${#missing[@]})); then
  say "Installing missing Termux packages: ${missing[*]}"
  if ! pkg install -y "${missing[@]}"; then
    retry=()
    for p in "${missing[@]}"; do
      [[ "$p" == "nodejs-lts" ]] && retry+=("nodejs") || retry+=("$p")
    done
    pkg install -y "${retry[@]}" ||
      die "Package provisioning failed. Repository signature verification was not bypassed."
  fi
fi

for c in git python sha256sum curl jq pgrep openssl node npm; do
  command -v "$c" >/dev/null 2>&1 || die "Required command still missing: $c"
done

if ! command -v termux-wake-lock >/dev/null 2>&1; then
  pkg install -y termux-api >/dev/null 2>&1 || true
fi

mkdir -p "$ROOT" "$STATE"

fetch_exact(){
  local sha="$1" dest="$2"
  if [[ -d "$dest/.git" ]] &&
     [[ "$(git -C "$dest" rev-parse HEAD 2>/dev/null || true)" == "$sha" ]] &&
     [[ -z "$(git -C "$dest" status --porcelain --untracked-files=all 2>/dev/null || true)" ]]; then
    printf '%s' "$dest"
    return 0
  fi
  if [[ -e "$dest" ]]; then
    dest="${dest}.preserved.${STAMP}"
  fi
  mkdir -p "$dest"
  git -C "$dest" init -q
  git -C "$dest" remote add origin "$REPO"
  git -C "$dest" fetch -q --depth 1 origin "$sha"
  git -C "$dest" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$dest" rev-parse HEAD)" == "$sha" ]] || die "Git pin mismatch for $sha"
  [[ -z "$(git -C "$dest" status --porcelain --untracked-files=all)" ]] ||
    die "Pinned checkout is dirty: $dest"
  printf '%s' "$dest"
}

say "Acquiring exact canonical installer source."
MAIN_SRC="$(fetch_exact "$MAIN_SHA" "$ROOT/main-$MAIN_SHA")"

say "Running canonical device-install smoke."
export CENTINAL26_ENABLE_BOOT_AUTOPILOT=0
bash "$MAIN_SRC/deploy/termux/CENTINAL26_FROST_ONE_PASTE_v1.0.sh"

say "Reviving any previously authorized remote bridge without requesting credentials again."
bridge="NONE"
if [[ -x "$HOME/.automation_bridge/bin/recovery-supervisor-start" ]]; then
  "$HOME/.automation_bridge/bin/recovery-supervisor-start" >/dev/null 2>&1 || true
  bridge="BASE44_RECOVERY"
elif command -v automation-recovery-start >/dev/null 2>&1; then
  automation-recovery-start >/dev/null 2>&1 || true
  bridge="BASE44_RECOVERY"
fi
if command -v frost-conversation-bridge-start >/dev/null 2>&1; then
  frost-conversation-bridge-start >/dev/null 2>&1 || true
  bridge="${bridge}+CONVERSATION"
fi
if [[ -x "$HOME/automation-intelligence-control-repo/termux/intelligence_node.sh" ]]; then
  "$HOME/automation-intelligence-control-repo/termux/intelligence_node.sh" start >/dev/null 2>&1 || true
  bridge="${bridge}+GITHUB_NODE"
fi
say "Bridge recovery: $bridge"

say "Acquiring exact host-qualified capability-first persistence source."
PERSIST_SRC="$(fetch_exact "$PERSIST_SHA" "$ROOT/persistence-$PERSIST_SHA")"

export CENTINAL26_HOME="$STATE"
say "Running physical pre-reboot campaign on this available phone."
bash "$PERSIST_SRC/scripts/device-validation-termux.sh"

identity="$(
  PYTHONPATH="$PERSIST_SRC/src${PYTHONPATH:+:$PYTHONPATH}" \
  python -S -m centinal26.device_campaign_cli identity
)"
device_id="$(printf '%s' "$identity" | python -c 'import json,sys; print(json.load(sys.stdin)["device_id"])')"
campaign="$STATE/device-validation/devices/$device_id/current"

[[ -f "$campaign/device-campaign-checkpoint.json" ]] ||
  die "Campaign checkpoint not found for $device_id"

boot_app="UNKNOWN"
if command -v pm >/dev/null 2>&1; then
  if pm list packages 2>/dev/null | grep -qx 'package:com.termux.boot'; then
    boot_app="INSTALLED"
  else
    boot_app="MISSING_ANDROID_APP"
  fi
fi

cat <<EOF

============================================================
CAPABILITY-FIRST PHONE BOOTSTRAP: PRE-REBOOT COMPLETE
============================================================
executor_device_id=$device_id
remote_bridge_recovered=$bridge
termux_boot_app=$boot_app
campaign=$campaign
source_commit=$PERSIST_SHA

Conversations/jobs are NOT pinned to this phone.
This phone was selected only because it executed this campaign.

If Termux:Boot is installed and enabled, reboot Android once.
The dedicated boot hook will resume the same evidence campaign.
Other phones may run other compatible work independently.

After reboot, verify:
  export PYTHONPATH="$PERSIST_SRC/src\${PYTHONPATH:+:\$PYTHONPATH}"
  python -S -m centinal26.device_campaign_cli verify --campaign "$campaign"
============================================================
EOF
