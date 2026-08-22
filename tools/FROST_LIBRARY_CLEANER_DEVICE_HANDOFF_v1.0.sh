#!/usr/bin/env bash
# Frost Library Cleaner physical-device handoff v1.0
# Canonical artifact is available in the associated validation package.
set -euo pipefail

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
  echo "ERROR: physical Android/Termux execution required" >&2
  exit 64
fi

echo "Frost Library Cleaner device handoff"
echo "This repository checkpoint records the physical-device boundary."
echo "Run the canonical validated handoff artifact on the Termux device, then preserve its evidence bundle."
exit 0
