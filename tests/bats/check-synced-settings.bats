#!/usr/bin/env bats

load helpers/setup

SCRIPT_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"

setup() {
  TEST_TEMP="$(mktemp -d)"
  export TEST_TEMP

  export REPO_DIR="$TEST_TEMP/repo"
  mkdir -p "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User"
  mkdir -p "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User"

  # Source the script (loads check_synced function without executing main)
  source "$SCRIPT_DIR/scripts/check-synced-settings.sh"
}

teardown() {
  rm -rf "$TEST_TEMP"
}

@test "identical files: no drift" {
  echo '{"a": 1}' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/settings.json"
  echo '{"a": 1}' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/settings.json"
  echo '[]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  run check_synced "$REPO_DIR"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "different content: reports DRIFT" {
  echo '{"a": 1}' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/settings.json"
  echo '{"a": 2}' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/settings.json"
  echo '[]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  check_synced "$REPO_DIR"
  [ "$DRIFT" -eq 1 ]
}

@test "missing linux copy: reports DRIFT" {
  # Only macos has settings.json
  echo '{"a": 1}' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/settings.json"
  echo '[]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  check_synced "$REPO_DIR"
  [ "$DRIFT" -eq 1 ]
}

@test "missing macos copy: reports DRIFT" {
  echo '{"a": 1}' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/settings.json"
  echo '[]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  check_synced "$REPO_DIR"
  [ "$DRIFT" -eq 1 ]
}

@test "both copies missing: no drift (pair not in use)" {
  # Only keybindings exist, settings don't — that's fine
  echo '[]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  run check_synced "$REPO_DIR"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "multiple drifts counted correctly" {
  echo '{"a": 1}' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/settings.json"
  echo '{"a": 2}' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/settings.json"
  echo '[1]' > "$REPO_DIR/linux/dotfiles/vscode/.config/Code/User/keybindings.json"
  echo '[2]' > "$REPO_DIR/macos/dotfiles/vscode/Library/Application Support/Code/User/keybindings.json"

  DRIFT=0
  check_synced "$REPO_DIR"
  [ "$DRIFT" -eq 2 ]
}
