#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

CENTINAL26_CANONICAL_GITHUB_REPO="12ephods-source/centinal26"
CENTINAL26_GITHUB_CONFIG_SCHEMA="centinal26-github-worker-config-v1"

validate_device_id() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9._:-]{1,128}$ ]]
}

github_runtime_write_config() {
  local config_path="$1" repo="$2" ref="$3" device_id="$4"
  [ "$repo" = "$CENTINAL26_CANONICAL_GITHUB_REPO" ] || {
    echo "BLOCKED_NONCANONICAL_REPO $repo" >&2
    return 64
  }
  [ "$ref" = "main" ] || {
    echo "BLOCKED_NONCANONICAL_REF $ref" >&2
    return 64
  }
  validate_device_id "$device_id" || {
    echo "BLOCKED_INVALID_DEVICE_ID" >&2
    return 64
  }
  command -v jq >/dev/null 2>&1 || {
    echo "BLOCKED_CONFIG_TOOL jq" >&2
    return 69
  }

  mkdir -p "$(dirname "$config_path")"
  local temp="${config_path}.tmp.$$"
  jq -n \
    --arg schema "$CENTINAL26_GITHUB_CONFIG_SCHEMA" \
    --arg repo "$repo" \
    --arg ref "$ref" \
    --arg device_id "$device_id" \
    '{schema:$schema,github_repo:$repo,github_ref:$ref,automation_device_id:$device_id}' \
    > "$temp"
  chmod 600 "$temp"
  mv "$temp" "$config_path"
}

github_runtime_load_config() {
  local config_path="$1"
  [ -f "$config_path" ] || {
    echo "Missing $config_path" >&2
    return 2
  }
  command -v jq >/dev/null 2>&1 || {
    echo "BLOCKED_CONFIG_TOOL jq" >&2
    return 69
  }
  command -v gh >/dev/null 2>&1 || {
    echo "BLOCKED_GITHUB_AUTH_TOOL gh" >&2
    return 69
  }

  jq -e \
    --arg schema "$CENTINAL26_GITHUB_CONFIG_SCHEMA" \
    --arg repo "$CENTINAL26_CANONICAL_GITHUB_REPO" \
    '.schema == $schema and
     .github_repo == $repo and
     .github_ref == "main" and
     (.automation_device_id | type == "string" and test("^[A-Za-z0-9._:-]{1,128}$"))' \
    "$config_path" >/dev/null || {
      echo "BLOCKED_INVALID_GITHUB_CONFIG" >&2
      return 64
    }

  GITHUB_REPO="$(jq -r '.github_repo' "$config_path")"
  GITHUB_REF="$(jq -r '.github_ref' "$config_path")"
  AUTOMATION_DEVICE_ID="$(jq -r '.automation_device_id' "$config_path")"
  GITHUB_TOKEN="$(gh auth token --hostname github.com 2>/dev/null || true)"
  [ -n "$GITHUB_TOKEN" ] || {
    echo "BLOCKED_GITHUB_AUTH" >&2
    return 2
  }
  export GITHUB_REPO GITHUB_REF AUTOMATION_DEVICE_ID GITHUB_TOKEN
}
