#!/usr/bin/env bash
set -euo pipefail
umask 077

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
# Guided secret collection (called from Phase 11 and re-run detection)
# =============================================================================

# Write plaintext to a SOPS-managed file and encrypt it in place.
# Creates the temp file in the target's directory so it matches .sops.yaml
# creation rules (path_regex: '.*/secrets/.*').
_write_and_encrypt() {
  local target="$1"
  local content="$2"
  local target_dir
  target_dir="$(dirname "$target")"
  local tmpfile
  tmpfile="$(mktemp "${target_dir}/.tmp.XXXXXX")"
  printf '%s\n' "$content" > "$tmpfile"
  if sops -e -i "$tmpfile"; then
    mv "$tmpfile" "$target"
    info "Encrypted $(basename "$target")"
  else
    rm -f "$tmpfile"
    error "Failed to encrypt $(basename "$target"). Plaintext was NOT written."
    return 1
  fi
}

edit_secrets() {
  echo ""
  gum style \
    --border normal \
    --border-foreground 6 \
    --padding "1 2" \
    "Secret Configuration" \
    "Press Enter to skip any value you don't have ready." \
    "Edit later with: make edit-secrets-shared"

  # ─── Shared vars ───────────────────────────────────────────────────────────
  echo ""
  info "Shared secrets (used on all platforms):"

  local shared_vars="$SCRIPT_DIR/shared/secrets/vars.sops.yml"
  local current_email=""
  if [ -f "$shared_vars" ]; then
    current_email=$(sops -d "$shared_vars" 2>/dev/null \
      | grep '^git_user_email:' \
      | sed 's/^git_user_email: *//' \
      | tr -d '"'"'" || true)
    [ "$current_email" = "PLACEHOLDER" ] && current_email=""
  fi

  local git_email
  git_email=$(gum input \
    --header "Git email${current_email:+ (current: $current_email)}" \
    --value "$current_email" \
    --placeholder "you@example.com")

  _write_and_encrypt "$shared_vars" "---
git_user_email: \"${git_email:-PLACEHOLDER}\""

  if [ -n "$git_email" ]; then
    info "git_user_email: $git_email"
  else
    info "git_user_email: skipped (edit later with: make edit-secrets-shared)"
  fi

  # ─── Shell secrets ─────────────────────────────────────────────────────────
  echo ""
  info "Shell secrets (exported in .zshrc via secrets.zsh):"

  local shell_file="$SCRIPT_DIR/shared/secrets/dotfiles/zsh/.config/zsh/secrets.zsh.sops"
  local shell_content=""

  # Show existing exports (masking values)
  if [ -f "$shell_file" ]; then
    local existing
    existing=$(sops -d "$shell_file" 2>/dev/null | grep '^export ' || true)
    if [ -n "$existing" ]; then
      info "Currently set:"
      echo "$existing" | sed 's/=.*/=***/'
      echo ""
    fi
    # Preserve existing content (excluding comments-only placeholder)
    local full_content
    full_content=$(sops -d "$shell_file" 2>/dev/null || true)
    if echo "$full_content" | grep -q '^export '; then
      shell_content="$full_content"
    fi
  fi

  while gum confirm "Add a shell secret (export KEY=\"value\")?"; do
    local key value
    key=$(gum input --header "Variable name" --placeholder "SOME_API_KEY")
    [ -z "$key" ] && continue
    value=$(gum input --header "Value for $key" --placeholder "value" --password)
    [ -z "$value" ] && { info "Skipped $key (empty value)."; continue; }
    if [ -z "$shell_content" ]; then
      shell_content="# Shell secrets — sourced by .zshrc"
    fi
    shell_content+=$'\n'"export ${key}=\"${value}\""
    info "Added $key"
  done

  if [ -n "$shell_content" ]; then
    _write_and_encrypt "$shell_file" "$shell_content"
  else
    info "No shell secrets added."
  fi

  # ─── Platform vars ─────────────────────────────────────────────────────────
  echo ""
  if [ "$PLATFORM" = "macos" ]; then
    info "macOS secrets: no keys defined yet."
  else
    info "Linux secrets: no keys defined yet."
  fi

  # ─── Summary ───────────────────────────────────────────────────────────────
  echo ""
  info "To edit secrets later:"
  info "  make edit-secrets-shared    # shared vars (git_user_email, etc.)"
  if [ "$PLATFORM" = "macos" ]; then
    info "  make edit-secrets-macos     # macOS-specific vars"
  else
    info "  make edit-secrets-linux     # Linux-specific vars"
  fi
  info "  Tip: EDITOR=nano make edit-secrets-shared"
}

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

  # sops (pinned version + checksum)
  if ! command -v sops &>/dev/null; then
    info "Installing sops..."
    local sops_version="3.9.4"
    local sops_sha256="e18a091c45888f82e1a7fd14561ebb913872441f92c8162d39bb63eb9308dd16"
    local sops_deb
    sops_deb="$(mktemp --suffix=.deb)"
    curl -fsSL "https://github.com/getsops/sops/releases/download/v${sops_version}/sops_${sops_version}_amd64.deb" -o "$sops_deb"
    local actual_sha256
    actual_sha256="$(sha256sum "$sops_deb" | awk '{print $1}')"
    if [ "$actual_sha256" != "$sops_sha256" ]; then
      rm -f "$sops_deb"
      error "sops checksum mismatch! Expected: $sops_sha256, Got: $actual_sha256"
      exit 1
    fi
    sudo dpkg -i "$sops_deb"
    rm -f "$sops_deb"
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

  # Homebrew — pin installer to a specific commit to prevent supply chain attacks.
  # Update this SHA when you want to pull in a newer installer version:
  #   git ls-remote https://github.com/Homebrew/install.git HEAD
  local brew_commit="0e1bf654fd95d1ddebe83b1f8c77de6e2c1b7cfe"
  if ! command -v brew &>/dev/null; then
    info "Installing Homebrew..."
    local brew_installer
    brew_installer="$(mktemp)"
    curl -fsSL "https://raw.githubusercontent.com/Homebrew/install/${brew_commit}/install.sh" -o "$brew_installer"
    /bin/bash "$brew_installer"
    rm -f "$brew_installer"
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

RESUME_MODE=false
if ! grep -q '${AGE_PUBLIC_KEY}' "$SCRIPT_DIR/.sops.yaml" 2>/dev/null; then
  # Determine what's incomplete.
  _has_origin=false
  _has_commit=false
  _is_pushed=false
  _has_precommit=false
  _pending=()

  if git remote get-url origin &>/dev/null; then _has_origin=true; fi
  if [ -f "$SCRIPT_DIR/.git/hooks/pre-commit" ]; then _has_precommit=true; fi
  # Check if personalization changes are committed (no diff in the files envsubst touches).
  if git diff --quiet -- .sops.yaml bootstrap.sh README.md 2>/dev/null && \
     git diff --quiet -- '*/secrets/*' 2>/dev/null; then
    _has_commit=true
  fi
  if $_has_origin && $_has_commit; then
    if git rev-parse --verify origin/main &>/dev/null && \
       [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] 2>/dev/null; then
      _is_pushed=true
    fi
  fi

  $_has_precommit || _pending+=("install pre-commit hooks")
  $_has_origin    || _pending+=("set up GitHub remote")
  $_has_commit    || _pending+=("commit personalized changes")
  $_is_pushed     || _pending+=("push to remote")

  # Check if secrets still contain placeholder values (Phase 11 never completed).
  _has_placeholder_secrets=false
  if grep -q 'PLACEHOLDER' "$SCRIPT_DIR/shared/secrets/vars.sops.yml" 2>/dev/null || \
     SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" sops -d "$SCRIPT_DIR/shared/secrets/vars.sops.yml" 2>/dev/null | grep -q 'PLACEHOLDER'; then
    _has_placeholder_secrets=true
  fi

  echo ""
  if [ ${#_pending[@]} -eq 0 ]; then
    if $_has_placeholder_secrets; then
      gum style --border normal --border-foreground 3 --padding "1 2" \
        "First-run is complete, but secrets still contain placeholders." \
        "  Origin: $(git remote get-url origin 2>/dev/null || echo 'not set')"
      edit_choice=$(gum choose \
        --header "What would you like to do?" \
        "Edit secrets now" \
        "Re-run everything from the beginning" \
        "Exit (edit later with: make edit-secrets-shared)")
      case "$edit_choice" in
        "Edit secrets"*)
          AGE_KEY_PATH="$HOME/.config/sops/age/keys.txt"
          export SOPS_AGE_KEY_FILE="$AGE_KEY_PATH"
          edit_secrets
          exit 0
          ;;
        "Re-run"*)
          ;;
        "Exit"*)
          info "Edit secrets later with: make edit-secrets-shared"
          exit 0
          ;;
      esac
    else
      gum style --border normal --border-foreground 2 --padding "1 2" \
        "First-run is already complete." \
        "  Origin: $(git remote get-url origin 2>/dev/null || echo 'not set')"
      if ! gum confirm "Re-run from the beginning anyway?"; then
        info "Nothing to do. Exiting."
        exit 0
      fi
    fi
  else
    pending_list=$(printf '  - %s\n' "${_pending[@]}")
    gum style --border normal --border-foreground 3 --padding "1 2" \
      "First-run was started but not finished. Remaining steps:" \
      "$pending_list"

    resume_choice=$(gum choose \
      --header "How would you like to proceed?" \
      "Resume from where it left off" \
      "Start over from the beginning" \
      "Exit")

    case "$resume_choice" in
      "Resume"*)
        RESUME_MODE=true
        ;;
      "Start over"*)
        ;;
      "Exit"*)
        info "Exiting."
        exit 0
        ;;
    esac
  fi
fi

# =============================================================================
# Phase 3: Generate age keypair
# =============================================================================

AGE_KEY_PATH="$HOME/.config/sops/age/keys.txt"
export SOPS_AGE_KEY_FILE="$AGE_KEY_PATH"
AGE_PUBLIC_KEY=""

if $RESUME_MODE; then
  # Extract existing values — no prompts needed for Phases 3-6.
  AGE_PUBLIC_KEY=$(grep -o 'age1[a-z0-9]*' "$AGE_KEY_PATH" | head -1 || true)
  if [ -z "$AGE_PUBLIC_KEY" ]; then
    AGE_PUBLIC_KEY=$(age-keygen -y "$AGE_KEY_PATH" 2>/dev/null || true)
  fi

  # Extract repo info from bootstrap.sh (envsubst already baked the URL in).
  GITHUB_REPO_URL=$(grep -o 'https://github\.com/[^"]*\.git' "$SCRIPT_DIR/bootstrap.sh" 2>/dev/null || echo "")
  if [ -z "$GITHUB_REPO_URL" ]; then
    # Fall back to origin remote.
    GITHUB_REPO_URL=$(git remote get-url origin 2>/dev/null | sed 's|git@github.com:|https://github.com/|; s|\.git$|.git|' || echo "")
  fi
  if [ -n "$GITHUB_REPO_URL" ]; then
    _repo_path="${GITHUB_REPO_URL##*github.com/}"
    _repo_path="${_repo_path%.git}"
    GITHUB_USERNAME="${_repo_path%%/*}"
    REPO_NAME="${_repo_path##*/}"
    info "Resuming: ${GITHUB_USERNAME}/${REPO_NAME}"
  else
    error "Could not determine repo info from bootstrap.sh or origin remote."
    exit 1
  fi
  export AGE_PUBLIC_KEY GITHUB_REPO_URL GITHUB_USERNAME REPO_NAME
else
  echo ""
  gum style \
    --border normal \
    --border-foreground 4 \
    --padding "1 2" \
    --margin "0 0 1 0" \
    "First-Run Setup"

  if [ -f "$AGE_KEY_PATH" ]; then
    info "Age key already exists at $AGE_KEY_PATH"
    AGE_PUBLIC_KEY=$(grep -o 'age1[a-z0-9]*' "$AGE_KEY_PATH" | head -1 || true)
    if [ -z "$AGE_PUBLIC_KEY" ]; then
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

  # ===========================================================================
  # Phase 4: Prompt for GitHub username + repo name
  # ===========================================================================

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

  # ===========================================================================
  # Phase 5: Replace tokens with envsubst
  # ===========================================================================

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

  # ===========================================================================
  # Phase 6: Encrypt all placeholder secret files
  # ===========================================================================

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
fi  # end of: if $RESUME_MODE ... else

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
    # Install uv first, then pre-commit — download then execute (not pipe-to-shell).
    # NOTE: No checksum verification here (bootstrap chicken-and-egg). The Ansible
    # python role pins uv to a specific version with SHA-256 verification.
    uv_installer="$(mktemp)"
    curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer"
    sh "$uv_installer"
    rm -f "$uv_installer"
    export PATH="$HOME/.local/bin:$PATH"
    uv tool install pre-commit
  fi
fi

# C1: Assert pre-commit is available — secrets cannot be committed without this guardrail
if ! command -v pre-commit &>/dev/null; then
  error "pre-commit installation failed. Cannot continue without secret-leak protection."
  exit 1
fi

if [ -d "$SCRIPT_DIR/.git" ]; then
  info "Installing pre-commit hooks..."
  cd "$SCRIPT_DIR" && pre-commit install
  if [ ! -f "$SCRIPT_DIR/.git/hooks/pre-commit" ]; then
    error "pre-commit hook not installed into .git/hooks/. Fix and re-run."
    exit 1
  fi
fi

# =============================================================================
# Phase 8: Detach from template repo
# =============================================================================

echo ""
cd "$SCRIPT_DIR"

if git remote get-url origin &>/dev/null; then
  current_origin=$(git remote get-url origin)
  # Compare owner/repo identity, not transport URL (SSH vs HTTPS).
  if [[ "$current_origin" == *"${GITHUB_USERNAME}/${REPO_NAME}"* ]]; then
    info "Remote 'origin' already points to ${GITHUB_USERNAME}/${REPO_NAME}."
  else
    warn "Current origin ($current_origin) does not match ${GITHUB_USERNAME}/${REPO_NAME}."
    if gum confirm "Replace origin remote?"; then
      git remote remove origin
    else
      info "Keeping existing origin."
    fi
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

    repo_visibility="--private"
    if gum confirm "Make the repo public? (Default: private)"; then
      repo_visibility="--public"
    fi

    # Create the repo if it doesn't already exist.
    if gh repo view "${GITHUB_USERNAME}/${REPO_NAME}" &>/dev/null; then
      info "GitHub repo ${GITHUB_USERNAME}/${REPO_NAME} already exists."
      git remote add origin "https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
    else
      info "Creating GitHub repo..."
      gh repo create "${GITHUB_USERNAME}/${REPO_NAME}" $repo_visibility --source . --remote origin
    fi
    info "Remote set to: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
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

  # Stage only tracked files + the specific files modified by envsubst/sops.
  # Avoids staging stray untracked files that could contain secrets.
  git add -u
  git add .sops.yaml bootstrap.sh README.md

  if git diff --cached --quiet; then
    info "Nothing to commit (already personalized)."
  else
    git commit -m "Initialize personalized workstation config"
  fi

  if git remote get-url origin &>/dev/null; then
    # Safety check: verify the remote is either empty or shares our history.
    remote_head=$(git ls-remote --refs origin HEAD 2>/dev/null | awk '{print $1}')
    if [ -n "$remote_head" ]; then
      if git merge-base --is-ancestor "$remote_head" HEAD 2>/dev/null || \
         git merge-base --is-ancestor HEAD "$remote_head" 2>/dev/null; then
        git push -u origin main
        info "Pushed to $(git remote get-url origin)"
      else
        warn "Remote has commits that don't share history with this repo."
        warn "Refusing to push. Verify that origin points to the correct repo."
        warn "  origin: $(git remote get-url origin)"
      fi
    else
      # Empty remote — first push.
      git push -u origin main
      info "Pushed to $(git remote get-url origin)"
    fi
  else
    info "Committed locally. Push when you've added a remote."
  fi
else
  info "Skipping commit. You can commit later with:"
  info "  git add -u && git commit -m 'Initialize personalized workstation config'"
fi

# =============================================================================
# Phase 11: Guided secret editing
# =============================================================================

edit_secrets

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
  "  1. Transfer age key to another machine:" \
  "     make send-key      (here — uses Magic Wormhole)" \
  "     make receive-key   (there)" \
  "  2. On the new machine:" \
  "     git clone $GITHUB_REPO_URL ~/.workstation" \
  "     cd ~/.workstation && make receive-key" \
  "     ./bootstrap.sh"
