#!/usr/bin/env bash
set -euo pipefail

# Transfer age private key between machines.
#
# Preferred: Magic Wormhole (e2e encrypted, zero-config, cross-platform)
#   Source:  ./scripts/transfer-key.sh send
#   Dest:   ./scripts/transfer-key.sh receive
#
# Fallback: Passphrase-encrypted blob (copy-paste, AirDrop, email, etc.)
#   Source:  ./scripts/transfer-key.sh export
#   Dest:   ./scripts/transfer-key.sh import
#
# Both methods layer passphrase encryption (age -p) on top of transport,
# so even if the channel is compromised the key remains protected.

AGE_KEY_PATH="${AGE_KEY_PATH:-$HOME/.config/sops/age/keys.txt}"

# Source wizard helpers if available (for info/warn/error), else define stubs.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
if [ -f "$REPO_DIR/shared/lib/wizard.sh" ]; then
  # shellcheck source=../shared/lib/wizard.sh
  source "$REPO_DIR/shared/lib/wizard.sh"
else
  info()  { echo "[INFO] $1"; }
  warn()  { echo "[WARN] $1"; }
  error() { echo "[ERROR] $1"; }
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

require_age() {
  if ! command -v age &>/dev/null; then
    error "age is not installed. Install it first:"
    error "  macOS: brew install age"
    error "  Linux: sudo apt install age"
    exit 1
  fi
}

require_key_exists() {
  if [ ! -f "$AGE_KEY_PATH" ]; then
    error "No age key found at $AGE_KEY_PATH"
    error "Nothing to send."
    exit 1
  fi
}

confirm_overwrite() {
  if [ ! -f "$AGE_KEY_PATH" ]; then
    return 0
  fi
  warn "Age key already exists at $AGE_KEY_PATH"
  if command -v gum &>/dev/null; then
    gum confirm "Overwrite existing key?" || { info "Cancelled."; exit 0; }
  else
    echo -n "Overwrite existing key? [y/N] "
    read -r answer
    [[ "$answer" == [yY]* ]] || { info "Cancelled."; exit 0; }
  fi
}

verify_imported_key() {
  local pub_key
  pub_key=$(age-keygen -y "$AGE_KEY_PATH" 2>/dev/null || true)
  if [ -n "$pub_key" ]; then
    info "Public key: $pub_key"
  else
    warn "Could not extract public key. Verify the key file is valid."
  fi
}

ensure_key_dir() {
  local key_dir
  key_dir="$(dirname "$AGE_KEY_PATH")"
  mkdir -p "$key_dir"
  chmod 700 "$key_dir"
}

# ---------------------------------------------------------------------------
# Magic Wormhole (preferred for mac-to-linux, any cross-platform transfer)
# ---------------------------------------------------------------------------

send_key() {
  require_key_exists
  require_age

  if ! command -v wormhole &>/dev/null; then
    error "Magic Wormhole is not installed. Install it first:"
    error "  macOS: brew install magic-wormhole"
    error "  Linux: pip install magic-wormhole  (or: sudo apt install magic-wormhole)"
    exit 1
  fi

  echo ""
  info "Encrypting key with a passphrase before sending..."
  info "You will be prompted to create a passphrase (enter it twice)."
  info "Share this passphrase through a SEPARATE channel (phone, in-person)."
  echo ""

  local tmpfile
  tmpfile="$(mktemp)"
  # shellcheck disable=SC2064
  trap "rm -f '$tmpfile'" EXIT

  age -p -a "$AGE_KEY_PATH" > "$tmpfile"

  echo ""
  info "Sending encrypted key via Magic Wormhole..."
  info "Give the wormhole code to the recipient."
  echo ""

  wormhole send "$tmpfile"
}

receive_key() {
  require_age
  confirm_overwrite

  if ! command -v wormhole &>/dev/null; then
    error "Magic Wormhole is not installed. Install it first:"
    error "  macOS: brew install magic-wormhole"
    error "  Linux: pip install magic-wormhole  (or: sudo apt install magic-wormhole)"
    exit 1
  fi

  local tmpfile
  tmpfile="$(mktemp)"
  # shellcheck disable=SC2064
  trap "rm -f '$tmpfile'" EXIT

  echo ""
  info "Enter the wormhole code from the sender."
  echo ""

  wormhole receive -o "$tmpfile" --accept-file

  echo ""
  info "Decrypting... (enter the passphrase from the sender)"

  ensure_key_dir
  age -d "$tmpfile" > "$AGE_KEY_PATH"
  chmod 600 "$AGE_KEY_PATH"

  info "Age key imported to $AGE_KEY_PATH"
  verify_imported_key
}

# ---------------------------------------------------------------------------
# Passphrase blob (fallback for AirDrop, email, paste, etc.)
# ---------------------------------------------------------------------------

export_key() {
  require_key_exists
  require_age

  echo ""
  info "Encrypting age key with a passphrase..."
  info "You will be prompted to enter a passphrase twice."
  info "Share the passphrase through a SEPARATE channel (phone, in-person)."
  echo ""

  local encrypted_blob
  encrypted_blob=$(age -p -a "$AGE_KEY_PATH")

  echo ""
  info "Encrypted key blob (copy everything between the markers):"
  echo ""
  echo "-----BEGIN AGE KEY TRANSFER-----"
  echo "$encrypted_blob"
  echo "-----END AGE KEY TRANSFER-----"
  echo ""
  info "On the destination machine, run:"
  info "  make import-key"
  info "Then paste the blob above (including the age-encryption.org header)."
}

import_key() {
  require_age
  confirm_overwrite

  echo ""
  info "Paste the encrypted key blob below."
  info "Include the '-----BEGIN AGE ENCRYPTED FILE-----' header."
  info "Press Ctrl-D when done."
  echo ""

  local blob
  blob=$(</dev/stdin)

  # Strip our transfer markers if the user copied those too.
  blob=$(echo "$blob" | grep -v '^\-\-\-\-\-BEGIN AGE KEY TRANSFER' | grep -v '^\-\-\-\-\-END AGE KEY TRANSFER')

  echo ""
  info "Decrypting... (enter the passphrase from the sender)"

  ensure_key_dir
  echo "$blob" | age -d > "$AGE_KEY_PATH"
  chmod 600 "$AGE_KEY_PATH"

  info "Age key imported to $AGE_KEY_PATH"
  verify_imported_key
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

usage() {
  echo "Usage: $0 <command>"
  echo ""
  echo "Magic Wormhole (preferred — cross-platform, e2e encrypted):"
  echo "  send      Encrypt and send the age key via Magic Wormhole"
  echo "  receive   Receive and decrypt the age key via Magic Wormhole"
  echo ""
  echo "Manual transfer (AirDrop, paste, email):"
  echo "  export    Encrypt and display the age key as a pasteable blob"
  echo "  import    Decrypt and install an age key from a pasted blob"
  exit 1
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-}" in
    send)    send_key ;;
    receive) receive_key ;;
    export)  export_key ;;
    import)  import_key ;;
    *)       usage ;;
  esac
fi
