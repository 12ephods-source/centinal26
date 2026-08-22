#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
umask 077

CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/frost-autopilot"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/frost-autopilot"
REGISTRY="${FROST_PROJECT_REGISTRY:-$CFG_DIR/projects.tsv}"
LOCK="$STATE_DIR/update.lock"
PROJECT=""
DO_ALL=0
INSTALL_PYTHON=0

mkdir -p "$CFG_DIR" "$STATE_DIR"
touch "$REGISTRY"
chmod 600 "$REGISTRY"

usage(){
  cat <<'EOF'
Usage:
  frost-autopilot-update --all [--install-python]
  frost-autopilot-update --project NAME [--install-python]
  frost-autopilot-update --register NAME PATH REMOTE BRANCH
  frost-autopilot-update --status

Security/update policy:
  * HTTPS/SSH Git remotes only.
  * Clean working tree required for automatic fast-forward.
  * No force reset, no rebase, no branch rewrite.
  * Divergence/dirty state becomes BLOCKED_LOCAL, preserving local work.
  * Repository tests may run after update; a failed test never claims success.
EOF
}

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$STATE_DIR/update.log"; }

register_project(){
  name="$1"; path="$2"; remote="$3"; branch="$4"
  case "$remote" in
    https://*|ssh://*|git@github.com:*) ;;
    *) echo "Refusing non-HTTPS/SSH remote: $remote" >&2; return 2 ;;
  esac
  tmp="$REGISTRY.tmp.$$"
  awk -F '\t' -v n="$name" '$1!=n' "$REGISTRY" > "$tmp" || true
  printf '%s\t%s\t%s\t%s\tff-only\n' "$name" "$path" "$remote" "$branch" >> "$tmp"
  mv "$tmp" "$REGISTRY"
  chmod 600 "$REGISTRY"
  log "REGISTERED name=$name path=$path branch=$branch"
}

update_one(){
  name="$1"; path="$2"; remote="$3"; branch="$4"; mode="${5:-ff-only}"
  [ "$mode" = "ff-only" ] || { log "BLOCKED_CONFIG name=$name unsupported_mode=$mode"; return 2; }
  case "$remote" in
    https://*|ssh://*|git@github.com:*) ;;
    *) log "BLOCKED_CONFIG name=$name bad_remote=$remote"; return 2 ;;
  esac
  if [ ! -d "$path/.git" ]; then
    mkdir -p "$(dirname "$path")"
    log "CLONE name=$name branch=$branch"
    git clone --filter=blob:none --branch "$branch" "$remote" "$path" || { log "FAILED_CLONE name=$name"; return 1; }
  fi
  (
    cd "$path"
    actual="$(git remote get-url origin 2>/dev/null || true)"
    [ "$actual" = "$remote" ] || { log "BLOCKED_REMOTE name=$name expected=$remote actual=$actual"; exit 2; }
    if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
      log "BLOCKED_LOCAL name=$name reason=dirty_worktree"; exit 3
    fi
    git fetch --prune origin "$branch"
    local_sha="$(git rev-parse HEAD)"
    remote_sha="$(git rev-parse "origin/$branch")"
    if [ "$local_sha" = "$remote_sha" ]; then
      log "CURRENT name=$name sha=$local_sha"
    elif git merge-base --is-ancestor "$local_sha" "$remote_sha"; then
      git merge --ff-only "$remote_sha"
      log "UPDATED name=$name from=$local_sha to=$remote_sha"
    else
      log "BLOCKED_LOCAL name=$name reason=non_fast_forward local=$local_sha remote=$remote_sha"; exit 4
    fi
    if [ "$INSTALL_PYTHON" -eq 1 ] && [ -f pyproject.toml ]; then
      python -m pip install -e . >/dev/null
      log "PYTHON_EDITABLE_INSTALLED name=$name sha=$(git rev-parse HEAD)"
    fi
    if [ "$name" = "centinal26" ] && [ -d portable/openquest-termux ]; then
      mkdir -p "$HOME/.local/bin"
      [ -f portable/openquest-termux/frost_autopilot_update.sh ] && install -m 700 portable/openquest-termux/frost_autopilot_update.sh "$HOME/.local/bin/frost-autopilot-update.next"
      [ -f portable/openquest-termux/centinal26_autopilot_bridge.sh ] && install -m 700 portable/openquest-termux/centinal26_autopilot_bridge.sh "$HOME/.local/bin/centinal26-autopilot"
      [ -f portable/openquest-termux/openquest_launcher.sh ] && install -m 700 portable/openquest-termux/openquest_launcher.sh "$HOME/.local/bin/openquest-rpg"
      if [ -f "$HOME/.local/bin/frost-autopilot-update.next" ]; then
        mv "$HOME/.local/bin/frost-autopilot-update.next" "$HOME/.local/bin/frost-autopilot-update"
        log "CONTROL_PLANE_REFRESHED name=$name sha=$(git rev-parse HEAD)"
      fi
    fi
    if [ "$name" = "centinal26" ] && [ -d openquest/tests ]; then
      python -m unittest discover -s openquest/tests -q
      python -m openquest.cli options >/dev/null
      log "OPENQUEST_GATE_PASS name=$name sha=$(git rev-parse HEAD)"
    fi
  )
}

status(){
  printf 'NAME\tPATH\tBRANCH\tSTATE\n'
  while IFS=$'\t' read -r name path remote branch mode; do
    [ -n "${name:-}" ] || continue
    if [ ! -d "$path/.git" ]; then state="MISSING";
    elif [ -n "$(git -C "$path" status --porcelain --untracked-files=normal)" ]; then state="DIRTY";
    else state="PRESENT"; fi
    printf '%s\t%s\t%s\t%s\n' "$name" "$path" "$branch" "$state"
  done < "$REGISTRY"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --all) DO_ALL=1; shift ;;
    --project) PROJECT="${2:?missing project}"; shift 2 ;;
    --install-python) INSTALL_PYTHON=1; shift ;;
    --register) [ "$#" -ge 5 ] || { usage; exit 2; }; register_project "$2" "$3" "$4" "$5"; exit $? ;;
    --status) status; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[ "$DO_ALL" -eq 1 ] || [ -n "$PROJECT" ] || { usage; exit 2; }
exec 9>"$LOCK"
flock -n 9 || { log "SKIP reason=update_already_running"; exit 0; }
matched=0
rc=0
while IFS=$'\t' read -r name path remote branch mode; do
  [ -n "${name:-}" ] || continue
  if [ "$DO_ALL" -eq 1 ] || [ "$name" = "$PROJECT" ]; then
    matched=1
    update_one "$name" "$path" "$remote" "$branch" "$mode" || rc=$?
  fi
done < "$REGISTRY"
[ "$matched" -eq 1 ] || { log "BLOCKED_CONFIG project_not_registered=$PROJECT"; exit 2; }
exit "$rc"
