#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HOME}/.frost-worker"
BOOT_DIR="${HOME}/.termux/boot"
CONFIG="${ROOT}/worker.json"
SECRET="${ROOT}/worker.secret"
REPO="${HOME}/centinal26"
QUEUE_URL="${FROST_QUEUE_URL:-}"
RESULT_URL="${FROST_RESULT_URL:-}"
DEVICE_ID="${FROST_DEVICE_ID:-$(getprop ro.serialno 2>/dev/null || true)}"
SOURCE_COMMIT="${FROST_SOURCE_COMMIT:-$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)}"

if [ -z "${QUEUE_URL}" ] || [ -z "${RESULT_URL}" ]; then
  printf 'FROST_QUEUE_URL and FROST_RESULT_URL are required.\n' >&2
  exit 2
fi
if [ -z "${DEVICE_ID}" ]; then
  printf 'Unable to determine device id; set FROST_DEVICE_ID.\n' >&2
  exit 2
fi
if ! printf '%s' "${SOURCE_COMMIT}" | grep -Eq '^[0-9a-fA-F]{40}$'; then
  printf 'FROST_SOURCE_COMMIT must be a full 40-character commit SHA.\n' >&2
  exit 2
fi

pkg install -y python termux-api termux-services
mkdir -p "${ROOT}" "${BOOT_DIR}"
chmod 700 "${ROOT}"

if [ ! -f "${SECRET}" ]; then
  python - <<'PY' "${SECRET}"
import secrets, pathlib, sys
path = pathlib.Path(sys.argv[1])
path.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
fi
chmod 600 "${SECRET}"

python - <<'PY' "${CONFIG}" "${DEVICE_ID}" "${SOURCE_COMMIT}" "${QUEUE_URL}" "${RESULT_URL}" "${SECRET}" "${ROOT}"
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
value = {
    "device_id": sys.argv[2],
    "source_commit": sys.argv[3].lower(),
    "queue_url": sys.argv[4],
    "result_url": sys.argv[5],
    "credential_path": sys.argv[6],
    "state_dir": sys.argv[7],
    "poll_seconds": 30,
    "max_backoff_seconds": 600,
}
path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
PY

cat > "${BOOT_DIR}/start-frost-worker.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
exec python "${REPO}/automation/device/outbound_worker.py" --config "${CONFIG}" >> "${ROOT}/worker.log" 2>&1
EOF
chmod 700 "${BOOT_DIR}/start-frost-worker.sh"

printf 'Outbound worker installed.\n'
printf 'device_id=%s\n' "${DEVICE_ID}"
printf 'source_commit=%s\n' "${SOURCE_COMMIT}"
printf 'credential_path=%s\n' "${SECRET}"
printf 'boot_launcher=%s\n' "${BOOT_DIR}/start-frost-worker.sh"
printf 'Controller must provision the matching device credential before jobs are accepted.\n'
