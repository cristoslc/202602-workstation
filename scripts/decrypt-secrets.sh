#!/usr/bin/env bash
set -euo pipefail

# Decrypt all .sops files in a secrets/ directory to .decrypted/ counterparts.
# Usage: ./scripts/decrypt-secrets.sh <secrets-dir>
# Example: ./scripts/decrypt-secrets.sh shared/secrets

SECRETS_DIR="${1:?Usage: $0 <secrets-dir>}"
DECRYPTED_DIR="$SECRETS_DIR/.decrypted"

if [ ! -d "$SECRETS_DIR" ]; then
  echo "Directory not found: $SECRETS_DIR"
  exit 1
fi

# Find all .sops and .sops.yml files (excluding .decrypted/ itself)
find "$SECRETS_DIR" -path "$DECRYPTED_DIR" -prune -o \( -name "*.sops" -o -name "*.sops.yml" -o -name "*.sops.yaml" \) -print | while read -r encrypted_file; do
  # Compute output path: replace secrets_dir with decrypted_dir, strip .sops suffix
  relative="${encrypted_file#$SECRETS_DIR/}"
  # For dotfiles: strip .sops extension. For vars files: keep .yml but strip .sops
  if [[ "$relative" == *.sops.yml ]] || [[ "$relative" == *.sops.yaml ]]; then
    decrypted_file="$DECRYPTED_DIR/${relative/.sops/}"
  else
    decrypted_file="$DECRYPTED_DIR/${relative%.sops}"
  fi

  # Create parent directory
  mkdir -p "$(dirname "$decrypted_file")"

  # Decrypt
  echo "Decrypting: $encrypted_file -> $decrypted_file"
  sops -d "$encrypted_file" > "$decrypted_file"
  chmod 600 "$decrypted_file"
done

echo "Done. Decrypted files are in $DECRYPTED_DIR/"
