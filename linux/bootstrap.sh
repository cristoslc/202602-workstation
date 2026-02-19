#!/usr/bin/env bash
set -euo pipefail

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

# Install sops
if ! command -v sops &>/dev/null; then
  info "Installing sops..."
  local_sops_version="3.9.4"
  curl -fsSL "https://github.com/getsops/sops/releases/download/v${local_sops_version}/sops_${local_sops_version}_amd64.deb" -o /tmp/sops.deb
  sudo dpkg -i /tmp/sops.deb
  rm -f /tmp/sops.deb
fi

# Install age
if ! command -v age &>/dev/null; then
  info "Installing age..."
  sudo apt-get install -y -qq age
fi

# Install gum
ensure_gum

# --- Phase 2: Install uv and Ansible ---

if ! command -v uv &>/dev/null; then
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
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
