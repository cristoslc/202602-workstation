#!/usr/bin/env bash
set -euo pipefail

# First-run setup: personalizes the template repo, generates age key, encrypts
# secrets, and pushes to your own GitHub repo.
# Usage: ./first-run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect platform
case "$(uname -s)" in
  Linux*)  PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  *)
    echo "Unsupported OS: $(uname -s)"
    exit 1
    ;;
esac

# Source shared helpers (info, warn, error, ensure_gum)
source "$SCRIPT_DIR/shared/lib/wizard.sh"

trap 'error "First-run failed. Fix the issue above and re-run."' ERR

# =============================================================================
# Phase 1: Self-bootstrap prerequisites
# =============================================================================

info "Checking and installing prerequisites..."

install_prereqs_linux() {
  sudo apt-get update -qq

  # age
  if ! command -v age &>/dev/null; then
    info "Installing age..."
    sudo apt-get install -y -qq age
  fi

  # envsubst (gettext-base)
  if ! command -v envsubst &>/dev/null; then
    info "Installing gettext-base (envsubst)..."
    sudo apt-get install -y -qq gettext-base
  fi

  # sops
  if ! command -v sops &>/dev/null; then
    info "Installing sops..."
    local sops_version="3.9.4"
    curl -fsSL "https://github.com/getsops/sops/releases/download/v${sops_version}/sops_${sops_version}_amd64.deb" -o /tmp/sops.deb
    sudo dpkg -i /tmp/sops.deb
    rm -f /tmp/sops.deb
  fi

  # gh CLI
  if ! command -v gh &>/dev/null; then
    info "Installing GitHub CLI..."
    sudo mkdir -p -m 755 /etc/apt/keyrings
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq gh
  fi

  # gum
  ensure_gum
}

install_prereqs_macos() {
  # Xcode CLT
  if ! xcode-select -p &>/dev/null; then
    info "Installing Xcode Command Line Tools..."
    xcode-select --install
    until xcode-select -p &>/dev/null; do sleep 5; done
  fi

  # Homebrew
  if ! command -v brew &>/dev/null; then
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi

  # Install all prereqs via brew
  info "Installing prerequisites via Homebrew..."
  brew install age sops gum gh gettext 2>/dev/null || true
}

if [ "$PLATFORM" = "linux" ]; then
  install_prereqs_linux
else
  install_prereqs_macos
fi

# =============================================================================
# Phase 2: Detect if already run
# =============================================================================

if ! grep -q '${AGE_PUBLIC_KEY}' "$SCRIPT_DIR/.sops.yaml" 2>/dev/null; then
  warn "This repo appears to be already configured (.sops.yaml has no template tokens)."
  if ! gum confirm "Re-run first-run anyway?"; then
    info "Nothing to do. Exiting."
    exit 0
  fi
fi

# =============================================================================
# Phase 3: Generate age keypair
# =============================================================================

AGE_KEY_PATH="$HOME/.config/sops/age/keys.txt"
AGE_PUBLIC_KEY=""

echo ""
gum style \
  --border normal \
  --border-foreground 4 \
  --padding "1 2" \
  --margin "0 0 1 0" \
  "First-Run Setup"

if [ -f "$AGE_KEY_PATH" ]; then
  info "Age key already exists at $AGE_KEY_PATH"
  # Extract public key from existing key file
  AGE_PUBLIC_KEY=$(grep -o 'age1[a-z0-9]*' "$AGE_KEY_PATH" | head -1 || true)
  if [ -z "$AGE_PUBLIC_KEY" ]; then
    # Try to get it from the recipient line
    AGE_PUBLIC_KEY=$(age-keygen -y "$AGE_KEY_PATH" 2>/dev/null || true)
  fi
  if [ -z "$AGE_PUBLIC_KEY" ]; then
    error "Could not extract public key from $AGE_KEY_PATH"
    exit 1
  fi
  info "Public key: $AGE_PUBLIC_KEY"
else
  info "Generating age keypair..."
  mkdir -p "$(dirname "$AGE_KEY_PATH")"
  AGE_KEYGEN_OUTPUT=$(age-keygen 2>&1)
  echo "$AGE_KEYGEN_OUTPUT" | grep -v "^Public key:" > "$AGE_KEY_PATH"
  chmod 700 "$(dirname "$AGE_KEY_PATH")"
  chmod 600 "$AGE_KEY_PATH"
  AGE_PUBLIC_KEY=$(echo "$AGE_KEYGEN_OUTPUT" | grep "^Public key:" | awk '{print $3}')
  info "Age keypair generated."
  info "Public key: $AGE_PUBLIC_KEY"
  echo ""
  gum style --foreground 3 \
    "Keep your private key safe! Back it up to a secure location." \
    "Path: $AGE_KEY_PATH"
fi

# =============================================================================
# Phase 4: Prompt for GitHub username + repo name
# =============================================================================

echo ""
GITHUB_USERNAME=$(gum input \
  --header "GitHub username" \
  --placeholder "your-username")

REPO_NAME=$(gum input \
  --header "Repository name" \
  --value "my-workstation" \
  --placeholder "my-workstation")

GITHUB_REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

info "Repo URL: $GITHUB_REPO_URL"

# =============================================================================
# Phase 5: Replace tokens with envsubst
# =============================================================================

echo ""
info "Personalizing configuration files..."

export AGE_PUBLIC_KEY GITHUB_REPO_URL GITHUB_USERNAME REPO_NAME

# MUST use explicit var lists — bootstrap.sh has ${BASH_SOURCE[0]} and ${1:-...}
# that envsubst would destroy without scoping
envsubst '${AGE_PUBLIC_KEY}' < "$SCRIPT_DIR/.sops.yaml" > "$SCRIPT_DIR/.sops.yaml.tmp"
mv "$SCRIPT_DIR/.sops.yaml.tmp" "$SCRIPT_DIR/.sops.yaml"

envsubst '${GITHUB_REPO_URL}' < "$SCRIPT_DIR/bootstrap.sh" > "$SCRIPT_DIR/bootstrap.sh.tmp"
mv "$SCRIPT_DIR/bootstrap.sh.tmp" "$SCRIPT_DIR/bootstrap.sh"
chmod +x "$SCRIPT_DIR/bootstrap.sh"

envsubst '${GITHUB_REPO_URL} ${GITHUB_USERNAME} ${REPO_NAME}' < "$SCRIPT_DIR/README.md" > "$SCRIPT_DIR/README.md.tmp"
mv "$SCRIPT_DIR/README.md.tmp" "$SCRIPT_DIR/README.md"

info "Tokens replaced in .sops.yaml, bootstrap.sh, and README.md"

# =============================================================================
# Phase 6: Encrypt all placeholder secret files
# =============================================================================

echo ""
info "Encrypting secret placeholder files..."

encrypted_count=0
while IFS= read -r -d '' sops_file; do
  # Skip .sops.yaml itself (the config file, not a secret)
  if [[ "$sops_file" == *".sops.yaml" ]] && [[ "$sops_file" != *"/secrets/"* ]]; then
    continue
  fi
  # Skip files that are already encrypted (contain sops metadata)
  if grep -q '"sops":' "$sops_file" 2>/dev/null || grep -q 'sops:' "$sops_file" 2>/dev/null; then
    info "  Already encrypted: $sops_file"
    continue
  fi
  info "  Encrypting: $sops_file"
  sops -e -i "$sops_file"
  ((encrypted_count++)) || true
done < <(find "$SCRIPT_DIR" -path '*/secrets/*' \( -name '*.sops.yml' -o -name '*.sops.yaml' -o -name '*.sops' \) -print0)

info "Encrypted $encrypted_count file(s)."

# =============================================================================
# Phase 7: Install pre-commit hooks
# =============================================================================

echo ""
if command -v pre-commit &>/dev/null; then
  info "pre-commit already installed."
else
  info "Installing pre-commit..."
  if command -v uv &>/dev/null; then
    uv tool install pre-commit
  elif command -v pip3 &>/dev/null; then
    pip3 install --user pre-commit
  else
    # Install uv first, then pre-commit
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    uv tool install pre-commit
  fi
fi

if [ -d "$SCRIPT_DIR/.git" ]; then
  info "Installing pre-commit hooks..."
  cd "$SCRIPT_DIR" && pre-commit install
fi

# =============================================================================
# Phase 8: Detach from template repo
# =============================================================================

echo ""
cd "$SCRIPT_DIR"

if git remote get-url origin &>/dev/null; then
  current_origin=$(git remote get-url origin)
  if [ "$current_origin" != "$GITHUB_REPO_URL" ]; then
    info "Removing template origin ($current_origin)..."
    git remote remove origin
  fi
fi

# =============================================================================
# Phase 9: Create user's GitHub repo
# =============================================================================

echo ""
if ! git remote get-url origin &>/dev/null; then
  if gum confirm "Create GitHub repo ${GITHUB_USERNAME}/${REPO_NAME}?"; then
    # Ensure gh is authenticated
    if ! gh auth status &>/dev/null 2>&1; then
      info "GitHub CLI needs authentication..."
      gh auth login
    fi

    info "Creating GitHub repo..."
    gh repo create "${GITHUB_USERNAME}/${REPO_NAME}" --public --source . --remote origin
    info "GitHub repo created: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
  else
    info "Skipping GitHub repo creation."
    info "You can add a remote later with:"
    info "  git remote add origin $GITHUB_REPO_URL"
  fi
else
  info "Remote 'origin' already set to: $(git remote get-url origin)"
fi

# =============================================================================
# Phase 10: Commit + push
# =============================================================================

echo ""
if gum confirm "Commit personalized changes and push?"; then
  cd "$SCRIPT_DIR"

  # Initialize git if needed
  if [ ! -d .git ]; then
    git init
    git branch -M main
  fi

  git add -A
  git commit -m "Initialize personalized workstation config"

  if git remote get-url origin &>/dev/null; then
    git push -u origin main
    info "Pushed to $(git remote get-url origin)"
  else
    info "Committed locally. Push when you've added a remote."
  fi
else
  info "Skipping commit. You can commit later with:"
  info "  git add -A && git commit -m 'Initialize personalized workstation config'"
fi

# =============================================================================
# Phase 11: Guided secret editing
# =============================================================================

echo ""
gum style \
  --border normal \
  --border-foreground 6 \
  --padding "1 2" \
  "Secrets are encrypted with placeholders." \
  "You can populate them with real values now," \
  "or do it later with: make edit-secrets-shared"

echo ""
if gum confirm "Edit shared secrets now?"; then
  sops "$SCRIPT_DIR/shared/secrets/vars.sops.yml"
fi

if gum confirm "Edit shared shell secrets (API keys, tokens for .zshrc)?"; then
  sops "$SCRIPT_DIR/shared/secrets/dotfiles/zsh/.config/zsh/secrets.zsh.sops"
fi

if gum confirm "Edit Linux secrets?"; then
  sops "$SCRIPT_DIR/linux/secrets/vars.sops.yml"
fi

if gum confirm "Edit Linux Espanso private matches?"; then
  sops "$SCRIPT_DIR/linux/secrets/dotfiles/espanso/.config/espanso/match/private.yml.sops"
fi

if gum confirm "Edit macOS secrets?"; then
  sops "$SCRIPT_DIR/macos/secrets/vars.sops.yml"
fi

# =============================================================================
# Done
# =============================================================================

echo ""
gum style \
  --border double \
  --border-foreground 2 \
  --padding "1 2" \
  --margin "1 0" \
  "First-run complete!" \
  "" \
  "Next steps:" \
  "  1. Distribute age key to other machines:" \
  "     $AGE_KEY_PATH" \
  "  2. On another machine:" \
  "     git clone $GITHUB_REPO_URL ~/.workstation" \
  "     # Copy age key into place" \
  "     cd ~/.workstation && ./bootstrap.sh"
