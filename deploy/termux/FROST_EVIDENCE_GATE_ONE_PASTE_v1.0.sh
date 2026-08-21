#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/12ephods-source/centinal26.git"
APP_ROOT="${HOME}/.local/share/frost-evidence-gate/repo"
STATE_ROOT="${FROST_EVIDENCE_STATE_ROOT:-${HOME}/.local/share/frost-evidence-gate}"
BIN_DIR="${HOME}/bin"
REF="${FROST_EVIDENCE_COLLECTOR_REF:-main}"

if [ -z "${PREFIX:-}" ] || [[ "${PREFIX}" != *com.termux* ]]; then
  printf 'ERROR: this installer must run inside Termux on Android.\n' >&2
  exit 2
fi

pkg update -y
pkg install -y git python coreutils curl age
if ! pkg install -y rclone; then
  printf 'WARNING: rclone is not installed; off-device round-trip remains blocked.\n' >&2
fi

mkdir -p "$(dirname "${APP_ROOT}")" "${STATE_ROOT}" "${BIN_DIR}"
chmod 700 "${STATE_ROOT}"

if [ -d "${APP_ROOT}/.git" ]; then
  git -C "${APP_ROOT}" fetch --all --prune
else
  git clone --filter=blob:none "${REPO_URL}" "${APP_ROOT}"
fi

if [ "${REF}" = "main" ]; then
  git -C "${APP_ROOT}" fetch origin main
  git -C "${APP_ROOT}" checkout -B frost-evidence-gate origin/main
else
  case "${REF}" in
    *[!0-9a-fA-F]*|'')
      printf 'ERROR: FROST_EVIDENCE_COLLECTOR_REF must be main or a full SHA.\n' >&2
      exit 2
      ;;
  esac
  if [ "${#REF}" -ne 40 ]; then
    printf 'ERROR: pinned collector SHA must be 40 characters.\n' >&2
    exit 2
  fi
  git -C "${APP_ROOT}" fetch --depth 1 origin "${REF}"
  git -C "${APP_ROOT}" checkout --detach --force "${REF}"
fi

COLLECTOR_SHA="$(git -C "${APP_ROOT}" rev-parse HEAD)"
COLLECTOR="${APP_ROOT}/automation/device/evidence_gate_collector.py"
if [ ! -f "${COLLECTOR}" ]; then
  printf 'ERROR: collector missing at selected revision %s.\n' "${COLLECTOR_SHA}" >&2
  exit 2
fi

cat > "${BIN_DIR}/frost-evidence-gate" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
COLLECTOR=${COLLECTOR@Q}
STATE_ROOT=${STATE_ROOT@Q}
# The generated Termux:Boot hook uses historical subcommand-first ordering.
# Normalize that one form before invoking argparse.
if [ "\${1:-}" = "post-reboot" ] && [ "\${2:-}" = "--state-root" ] && [ -n "\${3:-}" ]; then
  exec python "\${COLLECTOR}" --state-root "\${3}" post-reboot "\${@:4}"
fi
exec python "\${COLLECTOR}" "\$@"
EOF
chmod 700 "${BIN_DIR}/frost-evidence-gate"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    printf '\nexport PATH="$HOME/bin:$PATH"\n' >> "${HOME}/.bashrc"
    export PATH="${BIN_DIR}:${PATH}"
    ;;
esac

printf '\nCollector revision: %s\n' "${COLLECTOR_SHA}"
printf 'State root: %s\n\n' "${STATE_ROOT}"

"${BIN_DIR}/frost-evidence-gate" --state-root "${STATE_ROOT}" doctor

if command -v age-keygen >/dev/null 2>&1; then
  "${BIN_DIR}/frost-evidence-gate" --state-root "${STATE_ROOT}" init-age
fi

printf '\nInstalled command: frost-evidence-gate\n'
printf '\nRecommended sequence:\n'
printf '  1. frost-evidence-gate doctor\n'
printf '  2. frost-evidence-gate commission\n'
printf '  3. frost-evidence-gate worker-once --config /path/to/worker.json\n'
printf '  4. rclone config   # only if no external remote is configured yet\n'
printf '  5. frost-evidence-gate offdevice-roundtrip --source <commissioning.zip> --identity "%s/keys/age-identity.txt" --remote <remote:path>\n' "${STATE_ROOT}"
printf '  6. frost-evidence-gate arm-reboot --worker-config /path/to/worker.json\n'
printf '  7. Perform a PHYSICAL reboot from the device UI; do not use a remote reboot.\n'
printf '  8. frost-evidence-gate status\n\n'
printf 'The tool never marks an external or physical gate complete merely because host tests pass.\n'
