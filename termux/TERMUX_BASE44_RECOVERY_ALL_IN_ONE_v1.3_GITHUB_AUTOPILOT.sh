#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

VERSION="1.3"
CANONICAL_REPO="12ephods-source/centinal26"
REPO_ROOT="${CENTINAL26_REPO_ROOT:-$HOME/automation-intelligence-control-repo}"
STATE_ROOT="${TERMUX_REUSABLE_STATE_ROOT:-$HOME/.local/state/frost-termux-reusable}"
MODE="${1:-install}"

mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT" 2>/dev/null || true
LOG="$STATE_ROOT/run-$(date -u +%Y%m%dT%H%M%SZ).log"
STATUS="$STATE_ROOT/status.json"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 1; }

is_termux() { [ -n "${PREFIX:-}" ] && [[ "${PREFIX:-}" == /data/data/com.termux/files/usr* ]]; }
need() { command -v "$1" >/dev/null 2>&1; }

ensure_packages() {
  is_termux || fail "Run inside Termux; physical evidence may not be synthesized on a host."
  local missing=()
  need git || missing+=(git)
  need gh || missing+=(gh)
  need jq || missing+=(jq)
  need curl || missing+=(curl)
  need sha256sum || missing+=(coreutils)
  need python || missing+=(python)
  if [ "${#missing[@]}" -gt 0 ]; then
    need pkg || fail "pkg unavailable; missing: ${missing[*]}"
    pkg install -y "${missing[@]}"
  fi
}

github_auth() {
  if gh auth status --hostname github.com >/dev/null 2>&1; then
    log "GitHub auth: existing authenticated gh session"
    return 0
  fi
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    printf '%s\n' "$GITHUB_TOKEN" | gh auth login --hostname github.com --git-protocol https --with-token
    unset GITHUB_TOKEN
    log "GitHub auth: token consumed into gh credential store"
    return 0
  fi
  log "GitHub auth requires local user consent in Termux"
  gh auth login --hostname github.com --web --git-protocol https --scopes repo,workflow
}

sync_repo() {
  if [ -d "$REPO_ROOT/.git" ]; then
    [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has local changes; refusing automatic overwrite"
    git -C "$REPO_ROOT" fetch origin main
    git -C "$REPO_ROOT" checkout main
    git -C "$REPO_ROOT" merge --ff-only origin/main
  else
    gh repo clone "$CANONICAL_REPO" "$REPO_ROOT"
    git -C "$REPO_ROOT" checkout main
  fi
}

run_reusable_stack() {
  local installer="$REPO_ROOT/termux/install_intelligence_github_control.sh"
  local node="$REPO_ROOT/termux/intelligence_node.sh"
  [ -x "$installer" ] || chmod 700 "$installer" 2>/dev/null || true
  [ -x "$node" ] || chmod 700 "$node" 2>/dev/null || true
  [ -f "$installer" ] || fail "missing canonical GitHub/Termux installer"
  [ -f "$node" ] || fail "missing canonical Termux node"

  log "Installing/repairing canonical GitHub-aware Termux worker"
  CENTINAL26_REPO_ROOT="$REPO_ROOT" bash "$installer"
  log "Running reusable node doctor"
  CENTINAL26_REPO_ROOT="$REPO_ROOT" "$node" doctor | tee -a "$LOG"
  log "Kicking one bounded worker cycle"
  set +e
  CENTINAL26_REPO_ROOT="$REPO_ROOT" "$node" kick | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

write_status() {
  local rc="$1" commit="unknown" branch="unknown" gh_ok=false node_status='{}'
  [ -d "$REPO_ROOT/.git" ] && commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  [ -d "$REPO_ROOT/.git" ] && branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  gh auth status --hostname github.com >/dev/null 2>&1 && gh_ok=true
  if [ -x "$REPO_ROOT/termux/intelligence_node.sh" ]; then
    node_status="$(CENTINAL26_REPO_ROOT="$REPO_ROOT" "$REPO_ROOT/termux/intelligence_node.sh" status 2>/dev/null || echo '{}')"
  fi
  jq -n \
    --arg schema "frost.termux_reusable/github-autopilot-v1" \
    --arg version "$VERSION" \
    --arg repo "$CANONICAL_REPO" \
    --arg repo_commit "$commit" \
    --arg repo_branch "$branch" \
    --argjson github_authenticated "$gh_ok" \
    --argjson exit_code "$rc" \
    --argjson node "$node_status" \
    '{schema:$schema,version:$version,canonical_repo:$repo,repo_commit:$repo_commit,repo_branch:$repo_branch,github_authenticated:$github_authenticated,exit_code:$exit_code,physical_execution_claim:false,node:$node}' > "$STATUS.tmp"
  mv "$STATUS.tmp" "$STATUS"
  cat "$STATUS"
}

case "$MODE" in
  install|repair|autopilot)
    ensure_packages
    github_auth
    gh auth setup-git --hostname github.com
    sync_repo
    set +e
    run_reusable_stack
    rc=$?
    set -e
    write_status "$rc"
    exit "$rc"
    ;;
  doctor)
    ensure_packages
    github_auth
    sync_repo
    CENTINAL26_REPO_ROOT="$REPO_ROOT" "$REPO_ROOT/termux/intelligence_node.sh" doctor
    ;;
  status)
    ensure_packages
    write_status 0
    ;;
  *)
    echo "usage: $0 {install|repair|autopilot|doctor|status}" >&2
    exit 64
    ;;
esac
