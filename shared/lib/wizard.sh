#!/usr/bin/env bash
# Shared bootstrap wizard logic using gum.
# Sourced by platform-specific bootstrap scripts.
# Requires: gum is installed before sourcing this file.

# Colors for non-gum output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Run the bootstrap wizard. Sets exported variables:
#   BOOTSTRAP_MODE: fresh | new_account | existing_account
#   APPLY_SYSTEM_ROLES: true | false
#   APPLY_MACOS_DEFAULTS: true | false
#   SELECTED_PHASES: comma-separated list of phase tags
run_wizard() {
  echo ""
  gum style \
    --border normal \
    --border-foreground 4 \
    --padding "1 2" \
    --margin "0 0 1 0" \
    "Workstation Bootstrap"

  # Mode selection
  BOOTSTRAP_MODE=$(gum choose \
    --header "What kind of system is this?" \
    "Fresh install (new OS, clean slate)" \
    "Existing system, new user account" \
    "Existing system, existing user account")

  case "$BOOTSTRAP_MODE" in
    "Fresh install"*)
      BOOTSTRAP_MODE="fresh"
      APPLY_SYSTEM_ROLES=true
      APPLY_MACOS_DEFAULTS=true
      ;;
    "Existing system, new"*)
      BOOTSTRAP_MODE="new_account"
      APPLY_SYSTEM_ROLES=false
      APPLY_MACOS_DEFAULTS=true
      ;;
    "Existing system, existing"*)
      BOOTSTRAP_MODE="existing_account"
      APPLY_SYSTEM_ROLES=false
      APPLY_MACOS_DEFAULTS=false
      ;;
  esac

  # Role group selection
  local all_phases=("System" "Security" "Dev Tools" "Desktop" "Dotfiles")
  local default_phases

  if [ "$BOOTSTRAP_MODE" = "fresh" ]; then
    default_phases=("System" "Security" "Dev Tools" "Desktop" "Dotfiles")
  else
    default_phases=("Security" "Dev Tools" "Desktop" "Dotfiles")
  fi

  echo ""
  SELECTED_PHASES=$(gum choose \
    --no-limit \
    --header "Which role groups should run?" \
    --selected "$(IFS=,; echo "${default_phases[*]}")" \
    "${all_phases[@]}")

  # Override system roles based on selection
  if echo "$SELECTED_PHASES" | grep -q "System"; then
    APPLY_SYSTEM_ROLES=true
  else
    APPLY_SYSTEM_ROLES=false
  fi

  # Age key status
  echo ""
  if [ -f "$HOME/.config/sops/age/keys.txt" ]; then
    gum style --foreground 2 "Age key found at ~/.config/sops/age/keys.txt"
  else
    gum style --foreground 3 "Age key not found at ~/.config/sops/age/keys.txt"
    gum style --foreground 3 "Secrets decryption will be attempted via 1Password CLI."
    gum style --foreground 3 "If that fails, place your key and re-run bootstrap."
  fi

  # Summary
  echo ""
  gum style \
    --border normal \
    --border-foreground 6 \
    --padding "1 2" \
    "Mode: $BOOTSTRAP_MODE
System roles: $APPLY_SYSTEM_ROLES
Phases: $(echo "$SELECTED_PHASES" | tr '\n' ', ' | sed 's/,$//')"

  if ! gum confirm "Proceed with bootstrap?"; then
    echo "Bootstrap cancelled."
    exit 0
  fi

  export BOOTSTRAP_MODE
  export APPLY_SYSTEM_ROLES
  export APPLY_MACOS_DEFAULTS
  export SELECTED_PHASES
}

# Resolve the age private key.
# Returns 0 if key is available, 1 if not.
resolve_age_key() {
  local key_path="$HOME/.config/sops/age/keys.txt"
  local key_dir
  key_dir="$(dirname "$key_path")"

  # Already exists
  if [ -f "$key_path" ]; then
    chmod 700 "$key_dir"
    chmod 600 "$key_path"
    info "Age key found at $key_path"
    return 0
  fi

  # Try 1Password CLI
  if command -v op &>/dev/null; then
    info "Attempting to retrieve age key from 1Password..."
    mkdir -p "$key_dir"
    chmod 700 "$key_dir"
    if op read "op://Private/age-key/private-key" > "$key_path" 2>/dev/null; then
      chmod 600 "$key_path"
      info "Age key retrieved from 1Password."
      return 0
    else
      warn "Could not retrieve age key from 1Password (not signed in?)."
      rm -f "$key_path"
    fi
  fi

  # Neither available
  warn "Age key not available. Secrets will not be decrypted."
  warn "To enable secrets, place your age private key at:"
  warn "  $key_path"
  warn "Then re-run bootstrap."
  return 1
}

# Install gum if not present.
# Expects PLATFORM to be set (linux or macos).
ensure_gum() {
  if command -v gum &>/dev/null; then
    return 0
  fi

  info "Installing gum..."
  case "${PLATFORM:-}" in
    linux)
      # Install via .deb from GitHub releases
      local gum_version="0.14.5"
      local gum_deb="/tmp/gum_${gum_version}_amd64.deb"
      curl -fsSL "https://github.com/charmbracelet/gum/releases/download/v${gum_version}/gum_${gum_version}_amd64.deb" -o "$gum_deb"
      sudo dpkg -i "$gum_deb"
      rm -f "$gum_deb"
      ;;
    macos)
      brew install gum
      ;;
    *)
      error "Cannot install gum: unknown platform."
      exit 1
      ;;
  esac
}
