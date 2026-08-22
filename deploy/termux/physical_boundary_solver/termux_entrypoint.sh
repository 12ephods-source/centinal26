#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Canonical entrypoint for the physical-boundary solver.
#
# Problem addressed:
# Android/Termux can be genuine even when a parent process failed to preserve
# the PREFIX environment variable. PREFIX alone is therefore neither necessary
# nor sufficient evidence of device origin.
#
# This wrapper derives PREFIX only from the actually executing Termux bash path,
# after independent Android checks. It never fabricates device provenance and
# never promotes host/session execution to physical evidence.

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SOLVER="$ROOT/deploy/termux/physical_boundary_solver/run.sh"

fail() {
  printf 'FROST_PHYSICAL_RUNTIME_ERROR: %s\n' "$*" >&2
  exit 20
}

classify_runtime() {
  local bash_path prefix_candidate
  bash_path="$(command -v bash 2>/dev/null || true)"

  # Strong Android signals.
  command -v getprop >/dev/null 2>&1 || {
    printf 'HOST_OR_SESSION\n'
    return 0
  }
  [ -r /proc/sys/kernel/random/boot_id ] || {
    printf 'HOST_OR_SESSION\n'
    return 0
  }
  [ -n "$(getprop ro.build.version.release 2>/dev/null || true)" ] || {
    printf 'HOST_OR_SESSION\n'
    return 0
  }

  # Strong Termux signal: the bash binary itself must live in an Android app's
  # canonical files/usr tree. This cannot be satisfied merely by exporting
  # PREFIX in a host shell.
  case "$bash_path" in
    /data/data/*/files/usr/bin/bash)
      prefix_candidate="${bash_path%/bin/bash}"
      ;;
    *)
      printf 'ANDROID_NON_TERMUX_OR_UNVERIFIED\n'
      return 0
      ;;
  esac

  [ -x "$prefix_candidate/bin/bash" ] || {
    printf 'ANDROID_NON_TERMUX_OR_UNVERIFIED\n'
    return 0
  }
  [ -d "$prefix_candidate/etc" ] || {
    printf 'ANDROID_NON_TERMUX_OR_UNVERIFIED\n'
    return 0
  }

  printf 'ANDROID_TERMUX:%s\n' "$prefix_candidate"
}

runtime="$(classify_runtime)"

if [ "${1:-}" = "--classify" ]; then
  printf '%s\n' "$runtime"
  exit 0
fi

case "$runtime" in
  ANDROID_TERMUX:*)
    derived_prefix="${runtime#ANDROID_TERMUX:}"
    if [ -z "${PREFIX:-}" ]; then
      export PREFIX="$derived_prefix"
    elif [ "$PREFIX" != "$derived_prefix" ]; then
      fail "PREFIX disagrees with the verified Termux bash location."
    fi
    ;;
  HOST_OR_SESSION)
    fail "physical execution requires Android/Termux; host/session execution is not promoted"
    ;;
  ANDROID_NON_TERMUX_OR_UNVERIFIED)
    fail "Android was observed but the executing bash is not verified as Termux"
    ;;
  *)
    fail "unexpected runtime classifier output"
    ;;
esac

[ -f "$SOLVER" ] || fail "physical-boundary solver not found: $SOLVER"
"$PREFIX/bin/bash" -n "$SOLVER" || fail "physical-boundary solver failed syntax validation"

exec "$PREFIX/bin/bash" "$SOLVER" "$@"
