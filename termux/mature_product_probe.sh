#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

OUT="${1:-mature-product-device-evidence.json}"
ITERATIONS="${ENDURANCE_ITERATIONS:-100}"

if [ ! -r /proc/sys/kernel/random/boot_id ]; then
  echo "boot_id unavailable" >&2
  exit 2
fi

PRE_BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"

cat > "$OUT" <<EOF
{
  "schema": "frost.mature_product_device_evidence/v1",
  "platform": "android/termux",
  "pre_boot_id": "$PRE_BOOT_ID",
  "post_boot_id": "$PRE_BOOT_ID",
  "fresh_heartbeat": false,
  "bounded_job_completed": false,
  "independent_verification": false,
  "forbidden_capability_rejected": false,
  "post_reboot_heartbeat": false,
  "endurance_pass": false,
  "endurance_iterations": $ITERATIONS,
  "status": "PRE_REBOOT_CAPTURED"
}
EOF

sha256sum "$OUT" > "$OUT.sha256"
printf '%s\n' "Pre-reboot evidence captured: $OUT"
printf '%s\n' "Reboot the Android device, restart the verified Termux worker, then complete the existing bounded job/rejection/endurance gates before setting the corresponding fields true."
printf '%s\n' "Do not edit post_boot_id to a fabricated value; it must be captured from /proc/sys/kernel/random/boot_id after reboot."
