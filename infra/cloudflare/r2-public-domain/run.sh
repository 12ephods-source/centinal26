#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage:
  ./run.sh validate
  ./run.sh plan
  ./run.sh apply --authorize-publication
  ./run.sh output

plan/apply require CLOUDFLARE_API_TOKEN and terraform.tfvars.
apply only consumes an existing tfplan and requires the explicit
--authorize-publication acknowledgement because it creates/changes public
Cloudflare infrastructure.
EOF
}

require_terraform() {
  command -v terraform >/dev/null 2>&1 || {
    echo "ERROR: terraform is not installed or not on PATH" >&2
    exit 2
  }
}

require_apply_inputs() {
  [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || {
    echo "ERROR: CLOUDFLARE_API_TOKEN is not set" >&2
    exit 2
  }
  [[ -f terraform.tfvars ]] || {
    echo "ERROR: terraform.tfvars is missing; copy terraform.tfvars.example first" >&2
    exit 2
  }
}

init() {
  terraform init -input=false
}

cmd="${1:-validate}"
require_terraform

case "$cmd" in
  validate)
    terraform fmt -check -recursive
    terraform init -backend=false -input=false
    terraform validate
    ;;
  plan)
    require_apply_inputs
    init
    terraform validate
    terraform plan -input=false -out=tfplan
    echo "Plan written to $ROOT/tfplan"
    ;;
  apply)
    require_apply_inputs
    [[ "${2:-}" == "--authorize-publication" ]] || {
      echo "ERROR: apply requires --authorize-publication" >&2
      exit 2
    }
    [[ -f tfplan ]] || {
      echo "ERROR: tfplan is missing; run ./run.sh plan first" >&2
      exit 2
    }
    init
    terraform apply -input=false tfplan
    ;;
  output)
    terraform output
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
