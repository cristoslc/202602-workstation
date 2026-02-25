#!/usr/bin/env bash
set -euo pipefail

# Verify that app settings which must stay identical across platforms haven't drifted.
# Files deployed to different OS paths but sharing the same content are listed here.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(dirname "$SCRIPT_DIR")}"

DRIFT=0

# Each entry: <linux-relative-path> <macos-relative-path>
SYNCED_PAIRS=(
  "linux/dotfiles/vscode/.config/Code/User/settings.json"
  "macos/dotfiles/vscode/Library/Application Support/Code/User/settings.json"

  "linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  "macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"
)

check_synced() {
  local repo="$1"
  local i=0
  while [ $i -lt ${#SYNCED_PAIRS[@]} ]; do
    local linux_file="$repo/${SYNCED_PAIRS[$i]}"
    local macos_file="$repo/${SYNCED_PAIRS[$((i + 1))]}"
    local label="${SYNCED_PAIRS[$i]##*/}"

    if [ ! -f "$linux_file" ] && [ ! -f "$macos_file" ]; then
      # Neither exists — nothing to check.
      i=$((i + 2))
      continue
    fi

    if [ ! -f "$linux_file" ]; then
      echo "DRIFT: $label — missing linux copy: ${SYNCED_PAIRS[$i]}"
      DRIFT=$((DRIFT + 1))
    elif [ ! -f "$macos_file" ]; then
      echo "DRIFT: $label — missing macos copy: ${SYNCED_PAIRS[$((i + 1))]}"
      DRIFT=$((DRIFT + 1))
    elif ! diff -q "$linux_file" "$macos_file" >/dev/null 2>&1; then
      echo "DRIFT: $label — contents differ between platforms"
      diff --unified=3 "$linux_file" "$macos_file" | head -20
      DRIFT=$((DRIFT + 1))
    fi
    i=$((i + 2))
  done
}

# Allow sourcing for tests without executing main logic.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Checking cross-platform settings sync..."
  check_synced "$REPO_DIR"

  if [ "$DRIFT" -gt 0 ]; then
    echo ""
    echo "Found $DRIFT drifted file(s). Keep synced files identical across platforms."
    exit 1
  else
    echo "All synced settings are identical."
    exit 0
  fi
fi
