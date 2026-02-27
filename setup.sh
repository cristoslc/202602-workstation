#!/usr/bin/env bash
set -euo pipefail
umask 077

# Unified entry point: installs minimal prerequisites (python3, uv), then
# hands off to the Textual TUI for all interactive logic.
# Usage: ./setup.sh [--debug] [--bootstrap]
#   --bootstrap  Skip menu, go straight to bootstrap flow
#   Or via curl one-liner:
#     bash <(curl -fsSL https://raw.githubusercontent.com/.../setup.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install Xcode Command Line Tools headlessly via softwareupdate.
# xcode-select --install requires a GUI popup; this works over SSH too.
install_xcode_clt() {
  echo "Installing Xcode Command Line Tools..."
  local placeholder="/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress"
  touch "$placeholder"
  local label
  label="$(softwareupdate -l 2>/dev/null \
    | grep -o 'Label: Command Line Tools.*' \
    | sed 's/^Label: //' \
    | sort -rV \
    | head -n1)"
  if [ -z "$label" ]; then
    echo "Could not find Command Line Tools in softwareupdate catalog."
    rm -f "$placeholder"
    exit 1
  fi
  softwareupdate -i "$label"
  rm -f "$placeholder"
}

# Detect platform.
case "$(uname -s)" in
  Linux*)  PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  *)
    echo "Unsupported OS: $(uname -s)"
    exit 1
    ;;
esac
export PLATFORM

# Ensure ~/.local/bin is on PATH (uv installs there).
export PATH="$HOME/.local/bin:$PATH"

# --- Clone repo if running outside a cloned checkout ---

if [ ! -f "$SCRIPT_DIR/scripts/setup.py" ]; then
  WORKSTATION_DIR="${1:-$HOME/.workstation}"
  echo "Cloning repository to $WORKSTATION_DIR..."
  if [ "$PLATFORM" = "linux" ]; then
    sudo apt-get update -qq && sudo apt-get install -y -qq git curl
  else
    install_xcode_clt
  fi
  git clone "https://github.com/cristoslc/202602-workstation.git" "$WORKSTATION_DIR"
  exec "$WORKSTATION_DIR/setup.sh" "$@"
fi

# --- Ensure python3 is available ---

if [ "$PLATFORM" = "linux" ]; then
  if ! command -v python3 &>/dev/null; then
    echo "Installing python3..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3
  fi
else
  # macOS: Xcode CLT provides python3.
  if ! xcode-select -p &>/dev/null; then
    install_xcode_clt
  fi
fi

# --- Ensure uv is available ---

if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  uv_installer="$(mktemp)"
  curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer"
  sh "$uv_installer"
  rm -f "$uv_installer"
  export PATH="$HOME/.local/bin:$PATH"
fi

# --- Ensure sops + age are available (TUI state detection calls sops) ---

if [ "$PLATFORM" = "linux" ]; then
  if ! command -v age &>/dev/null; then
    echo "Installing age..."
    sudo apt-get install -y -qq age
  fi
  if ! command -v sops &>/dev/null; then
    echo "Installing sops v3.9.4..."
    sops_deb="$(mktemp --suffix=.deb)"
    curl -fsSL "https://github.com/getsops/sops/releases/download/v3.9.4/sops_3.9.4_amd64.deb" \
      -o "$sops_deb"
    expected="e18a091c45888f82e1a7fd14561ebb913872441f92c8162d39bb63eb9308dd16"
    actual="$(sha256sum "$sops_deb" | cut -d' ' -f1)"
    if [ "$actual" != "$expected" ]; then
      rm -f "$sops_deb"
      echo "sops checksum mismatch! Expected: $expected, Got: $actual"
      exit 1
    fi
    sudo dpkg -i "$sops_deb"
    rm -f "$sops_deb"
  fi
else
  # macOS: Homebrew (idempotent — skips already-installed).
  if command -v brew &>/dev/null; then
    brew install sops age rsync 2>/dev/null || true
  fi
fi

# --- Hand off to the Textual TUI ---

uv run --python 3.12 --with textual,pyyaml,jinja2 "$SCRIPT_DIR/scripts/setup.py" "$@" || tui_exit=$?
tui_exit="${tui_exit:-0}"

# Exit code 7 = bootstrap succeeded, reload shell to pick up new dotfiles.
if [ "$tui_exit" -eq 7 ]; then
  echo "Reloading shell to apply updated configs..."
  exec "${SHELL:-/bin/bash}" -l
fi

exit "$tui_exit"
