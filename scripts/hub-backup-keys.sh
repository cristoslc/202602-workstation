#!/usr/bin/env bash
# shellcheck shell=bash
# Backup Syncthing hub identity keys (age-encrypted) to the repo.
# Usage: scripts/hub-backup-keys.sh <hub-host>
set -euo pipefail

# ---------------------------------------------------------------------------
# Source guard for testability
# ---------------------------------------------------------------------------
_HUB_BACKUP_KEYS_SOURCED=1
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _HUB_BACKUP_KEYS_SOURCED=0
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SYNCTHING_HUB_USER="syncthing"
SYNCTHING_CONFIG_DIR="/home/${SYNCTHING_HUB_USER}/.local/state/syncthing"
KEY_FILES=(cert.pem key.pem)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${REPO_DIR}/shared/secrets/syncthing-hub-keys"

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
hub_backup_keys_usage() {
  cat <<'EOF'
Usage: scripts/hub-backup-keys.sh <hub-host>

Backup Syncthing hub identity keys (cert.pem, key.pem) from the hub server.
Keys are age-encrypted and stored at shared/secrets/syncthing-hub-keys/.

The age public key is read from .sops.yaml in the repo root.

Examples:
  make hub-backup-keys HUB_HOST=100.64.0.1
  scripts/hub-backup-keys.sh 100.64.0.1
EOF
}

hub_backup_keys_get_age_pubkey() {
  local sops_file="${REPO_DIR}/.sops.yaml"
  if [[ ! -f "$sops_file" ]]; then
    echo "ERROR: .sops.yaml not found at $sops_file" >&2
    return 1
  fi
  grep -oP "age1[a-z0-9]+" "$sops_file" | head -1
}

hub_backup_keys_check_ssh() {
  local host="$1"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null; then
    echo "ERROR: Cannot connect to '$host' via SSH."
    echo "Ensure SSH key auth is configured and the host is reachable."
    return 1
  fi
}

hub_backup_keys_check_age() {
  if ! command -v age &>/dev/null; then
    echo "ERROR: 'age' command not found. Install it first."
    echo "  macOS: brew install age"
    echo "  Linux: apt install age"
    return 1
  fi
}

hub_backup_keys_main() {
  local hub_host="${1:-}"

  if [[ -z "$hub_host" || "$hub_host" == "-h" || "$hub_host" == "--help" ]]; then
    hub_backup_keys_usage
    exit 1
  fi

  hub_backup_keys_check_age
  hub_backup_keys_check_ssh "$hub_host"

  local age_pubkey
  age_pubkey="$(hub_backup_keys_get_age_pubkey)"
  if [[ -z "$age_pubkey" ]]; then
    echo "ERROR: Could not extract age public key from .sops.yaml"
    exit 1
  fi

  echo "Hub host:   $hub_host"
  echo "Age pubkey: ${age_pubkey:0:12}..."
  echo "Output dir: $OUTPUT_DIR"
  echo ""

  mkdir -p "$OUTPUT_DIR"

  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  for keyfile in "${KEY_FILES[@]}"; do
    local remote_path="${SYNCTHING_CONFIG_DIR}/${keyfile}"
    local local_tmp="${tmpdir}/${keyfile}"
    local encrypted="${OUTPUT_DIR}/${keyfile}.age"

    echo "@@KEY_START:${keyfile}@@"
    echo "Downloading ${keyfile} from ${hub_host}..."
    scp -o BatchMode=yes "$hub_host:$remote_path" "$local_tmp"

    echo "Encrypting ${keyfile} with age..."
    age -r "$age_pubkey" -o "$encrypted" "$local_tmp"

    echo "@@KEY_DONE:${keyfile}@@"
  done

  echo ""
  echo "@@VERIFY_START@@"
  echo "Verifying encrypted files..."
  for keyfile in "${KEY_FILES[@]}"; do
    local encrypted="${OUTPUT_DIR}/${keyfile}.age"
    if [[ -f "$encrypted" ]]; then
      local size
      size="$(wc -c < "$encrypted" | tr -d ' ')"
      echo "  ${keyfile}.age: ${size} bytes"
    else
      echo "  ERROR: ${keyfile}.age not found!"
      exit 1
    fi
  done
  echo "@@VERIFY_DONE@@"

  echo ""
  echo "=== Hub key backup complete. ==="
  echo "Encrypted keys at: $OUTPUT_DIR"
  echo ""
  echo "To decrypt (for hub restore):"
  echo "  age -d -i ~/.config/sops/age/keys.txt ${OUTPUT_DIR}/cert.pem.age > /tmp/cert.pem"
  echo "  age -d -i ~/.config/sops/age/keys.txt ${OUTPUT_DIR}/key.pem.age > /tmp/key.pem"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ "$_HUB_BACKUP_KEYS_SOURCED" -eq 0 ]]; then
  hub_backup_keys_main "$@"
fi
