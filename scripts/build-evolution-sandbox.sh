#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${CENTINAL26_SANDBOX_IMAGE:-centinal26-evolution-validator:local}"
PYTEST_VERSION="${CENTINAL26_SANDBOX_PYTEST_VERSION:-9.1.1}"

if ! command -v docker >/dev/null 2>&1; then
  printf 'BLOCKED: Docker is required to build the controlled-evolution validator image.\n' >&2
  exit 2
fi

docker build \
  --build-arg "PYTEST_VERSION=$PYTEST_VERSION" \
  --tag "$IMAGE" \
  -f "$ROOT/deploy/evolution/Dockerfile" \
  "$ROOT"

image_id="$(docker image inspect --format '{{.Id}}' "$IMAGE")"
case "$image_id" in
  sha256:*) ;;
  *)
    printf 'BLOCKED: validator image did not resolve to a sha256 identity.\n' >&2
    exit 3
    ;;
esac

printf 'CENTINAL26_SANDBOX_IMAGE=%s\n' "$IMAGE"
printf 'CENTINAL26_SANDBOX_IMAGE_ID=%s\n' "$image_id"
