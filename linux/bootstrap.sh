#!/usr/bin/env bash
set -euo pipefail
umask 077

WORKSTATION_DIR="${1:-$HOME/.workstation}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="linux"

# Source shared wizard
source "$SCRIPT_DIR/../shared/lib/wizard.sh"

trap 'error "Bootstrap failed. Re-run after fixing the issue above."' ERR

# --- Phase 1: Install minimal prerequisites ---

info "Installing prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3 \
  python3-venv \
  curl \
  stow

# Install sops (pinned version + checksum)
if ! command -v sops &>/dev/null; then
  info "Installing sops..."
  sops_version="3.9.4"
  sops_sha256="e18a091c45888f82e1a7fd14561ebb913872441f92c8162d39bb63eb9308dd16"
  sops_deb="$(mktemp --suffix=.deb)"
  curl -fsSL "https://github.com/getsops/sops/releases/download/v${sops_version}/sops_${sops_version}_amd64.deb" -o "$sops_deb"
  actual_sha256="$(sha256sum "$sops_deb" | awk '{print $1}')"
  if [ "$actual_sha256" != "$sops_sha256" ]; then
    rm -f "$sops_deb"
    error "sops checksum mismatch! Expected: $sops_sha256, Got: $actual_sha256"
    exit 1
  fi
  sudo dpkg -i "$sops_deb"
  rm -f "$sops_deb"
fi

# Install age
if ! command -v age &>/dev/null; then
  info "Installing age..."
  sudo apt-get install -y -qq age
fi

# Install gum
ensure_gum

# --- Phase 2: Install uv and Ansible ---

# NOTE: uv is bootstrapped without checksum verification here because Ansible
# (installed via uv) is not yet available. The Ansible python role pins uv to a
# specific version with SHA-256 verification for subsequent installs.
if ! command -v uv &>/dev/null; then
  info "Installing uv..."
  uv_installer="$(mktemp)"
  curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer"
  sh "$uv_installer"
  rm -f "$uv_installer"
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v ansible-playbook &>/dev/null; then
  info "Installing Ansible via uv..."
  uv tool install ansible-core
fi

# --- Phase 3: Install Ansible Galaxy collections ---

info "Installing Ansible Galaxy collections..."
ansible-galaxy collection install -r "$SCRIPT_DIR/../shared/requirements.yml" --force

# --- Phase 4: Run wizard ---

run_wizard

# --- Phase 5: Resolve age key ---

resolve_age_key || true  # Non-fatal: secrets just won't decrypt

# --- Phase 6: Run Ansible ---

info "Running Ansible playbook..."
export ANSIBLE_CONFIG="$SCRIPT_DIR/ansible.cfg"
cd "$SCRIPT_DIR"

ansible-playbook site.yml \
  --ask-become-pass \
  -e "workstation_dir=$WORKSTATION_DIR" \
  -e "bootstrap_mode=$BOOTSTRAP_MODE" \
  -e "apply_system_roles=$APPLY_SYSTEM_ROLES" \
  -e "platform=linux" \
  -e "platform_dir=linux"

info "Bootstrap complete!"
info "Log out and back in for shell changes to take effect."
