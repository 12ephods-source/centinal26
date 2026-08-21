#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/12ephods-source/centinal26.git"
WORKDIR="${HOME}/centinal26"
TERMUX_KEY_COMMIT="625e1c90f5110842ec5d2e1fda677abdb5edfbed"
TERMUX_KEY_SHA256="21c385d5a30107453bd60582d64e2f6e5f5ce11e340ac05e57f943f9c0235420"
TERMUX_KEY_URL="https://raw.githubusercontent.com/termux/termux-packages/${TERMUX_KEY_COMMIT}/packages/termux-keyring/termux-autobuilds.gpg"
DEVICE_ID="${1:-$(getprop ro.serialno 2>/dev/null || true)}"
SOURCE_COMMIT="${2:-${FROST_SOURCE_COMMIT:-}}"
if [ -z "${DEVICE_ID}" ] || [ "${DEVICE_ID}" = "unknown" ]; then
  DEVICE_ID="$(getprop ro.product.manufacturer 2>/dev/null || echo android)-$(getprop ro.product.model 2>/dev/null || echo device)-$(date -u +%Y%m%dT%H%M%SZ)"
fi

repair_termux_keyring() {
  command -v curl >/dev/null 2>&1 || return 1
  local keydir="${PREFIX}/etc/apt/trusted.gpg.d"
  local tmp="${TMPDIR:-${PREFIX}/tmp}/termux-autobuilds.gpg"
  mkdir -p "${keydir}" "$(dirname "${tmp}")"
  curl -fsSL "${TERMUX_KEY_URL}" -o "${tmp}"
  printf '%s  %s\n' "${TERMUX_KEY_SHA256}" "${tmp}" | sha256sum -c -
  install -m 600 "${tmp}" "${keydir}/termux-autobuilds.gpg"
}

if ! pkg update -y; then
  printf '\nInitial Termux package update failed; attempting pinned keyring recovery.\n' >&2
  repair_termux_keyring
  pkg update -y
fi
pkg install -y git python coreutils curl

if [ -d "${WORKDIR}/.git" ]; then
  git -C "${WORKDIR}" fetch --all --prune
else
  git clone --depth 1 "${REPO_URL}" "${WORKDIR}"
fi

if [ -n "${SOURCE_COMMIT}" ]; then
  case "${SOURCE_COMMIT}" in
    *[!0-9a-fA-F]*|'')
      printf 'Invalid source commit: %s\n' "${SOURCE_COMMIT}" >&2
      exit 2
      ;;
  esac
  if [ "${#SOURCE_COMMIT}" -ne 40 ]; then
    printf 'Source commit must be a full 40-character SHA: %s\n' "${SOURCE_COMMIT}" >&2
    exit 2
  fi
  git -C "${WORKDIR}" fetch --depth 1 origin "${SOURCE_COMMIT}"
  git -C "${WORKDIR}" reset --hard "${SOURCE_COMMIT}"
else
  git -C "${WORKDIR}" reset --hard origin/main
fi

cd "${WORKDIR}"
SOURCE_COMMIT_ACTUAL="$(git rev-parse HEAD)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${HOME}/guardian_physical_validation_${STAMP}"
python automation/deployment/enrollment_package/capture_device_evidence.py \
  --device-id "${DEVICE_ID}" \
  --source-commit "${SOURCE_COMMIT_ACTUAL}" \
  --output "${OUT}"

printf '\nEvidence bundle: %s\n' "${OUT}"
python - <<'PY' "${OUT}"
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "MANIFEST.sha256.json").read_text())
errors = []
for name, expected in manifest["files"].items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != expected:
        errors.append({"file": name, "expected": expected, "actual": actual})
report = json.loads((root / "validation_report.json").read_text())
print(json.dumps({
    "manifest_verified": not errors,
    "errors": errors,
    "device_status": report["status"],
    "physical_device_gate": report["physical_device_gate"],
    "source_commit": report.get("source_commit"),
    "bundle": str(root),
}, indent=2))
raise SystemExit(1 if errors else 0)
PY

printf '\nTo return the evidence to ChatGPT, attach the entire directory as a zip:\n'
ZIP="${OUT}.zip"
python - <<'PY' "${OUT}" "${ZIP}"
import pathlib, shutil, sys
root = pathlib.Path(sys.argv[1])
zip_path = pathlib.Path(sys.argv[2])
base = zip_path.with_suffix("")
shutil.make_archive(str(base), "zip", root.parent, root.name)
print(zip_path)
PY
