#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/12ephods-source/centinal26.git"
WORKDIR="${HOME}/centinal26"
DEVICE_ID="${1:-$(getprop ro.serialno 2>/dev/null || true)}"
if [ -z "${DEVICE_ID}" ] || [ "${DEVICE_ID}" = "unknown" ]; then
  DEVICE_ID="$(getprop ro.product.manufacturer 2>/dev/null || echo android)-$(getprop ro.product.model 2>/dev/null || echo device)-$(date -u +%Y%m%dT%H%M%SZ)"
fi

pkg update -y
pkg install -y git python coreutils

if [ -d "${WORKDIR}/.git" ]; then
  git -C "${WORKDIR}" fetch --all --prune
  git -C "${WORKDIR}" reset --hard origin/main
else
  git clone --depth 1 "${REPO_URL}" "${WORKDIR}"
fi

cd "${WORKDIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${HOME}/guardian_physical_validation_${STAMP}"
python automation/deployment/enrollment_package/capture_device_evidence.py \
  --device-id "${DEVICE_ID}" \
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
