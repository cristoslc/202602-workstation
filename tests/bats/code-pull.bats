#!/usr/bin/env bats

load helpers/setup

SCRIPT_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"

setup() {
  TEST_TEMP="$(mktemp -d)"
  export TEST_TEMP

  # Source the script (loads functions without executing main)
  source "$SCRIPT_DIR/scripts/code-pull.sh"
}

teardown() {
  rm -rf "$TEST_TEMP"
}

# --- Configuration ---

@test "CODE_DIR defaults to ~/code" {
  unset CODE_DIR
  source "$SCRIPT_DIR/scripts/code-pull.sh"
  [[ "$CODE_DIR" == "$HOME/code" ]]
}

@test "CODE_DIR can be overridden" {
  export CODE_DIR="/tmp/my-code"
  source "$SCRIPT_DIR/scripts/code-pull.sh"
  [[ "$CODE_DIR" == "/tmp/my-code" ]]
}

@test "RSYNC_OPTS contains --partial" {
  local opts="${RSYNC_OPTS[*]}"
  [[ "$opts" == *"--partial"* ]]
}

@test "RSYNC_OPTS contains --partial-dir" {
  local opts="${RSYNC_OPTS[*]}"
  [[ "$opts" == *"--partial-dir=.rsync-partial"* ]]
}

# --- code_pull_usage ---

@test "usage: includes --scan-only option" {
  run code_pull_usage
  [ "$status" -eq 0 ]
  [[ "$output" == *"--scan-only"* ]]
}

@test "usage: includes --dry-run option" {
  run code_pull_usage
  [ "$status" -eq 0 ]
  [[ "$output" == *"--dry-run"* ]]
}

@test "usage: includes make code-pull example" {
  run code_pull_usage
  [ "$status" -eq 0 ]
  [[ "$output" == *"make code-pull"* ]]
}

# --- code_pull_clone_repo ---

@test "clone: skips if repo already exists locally" {
  export CODE_DIR="$TEST_TEMP/code"
  mkdir -p "$CODE_DIR/my-repo"

  run code_pull_clone_repo "fakehost" "my-repo" "false"
  [ "$status" -eq 0 ]
  [[ "$output" == *"already exists"* ]]
  [[ "$output" == *"@@REPO_SKIP:my-repo@@"* ]]
}

@test "clone: dry run emits clone marker" {
  export CODE_DIR="$TEST_TEMP/code"

  code_pull_get_remote_url() { echo "https://github.com/user/repo.git"; }

  run code_pull_clone_repo "fakehost" "my-repo" "true"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would clone from: https://github.com/user/repo.git"* ]]
  [[ "$output" == *"@@REPO_CLONE:my-repo:dry@@"* ]]
}

# --- code_pull_rsync_repo ---

@test "rsync: dry run emits rsync marker" {
  export CODE_DIR="$TEST_TEMP/code"

  run code_pull_rsync_repo "fakehost" "dirty-repo" "true"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Would rsync"* ]]
  [[ "$output" == *"@@REPO_RSYNC:dirty-repo:dry@@"* ]]
}

# --- code_pull_main argument parsing ---

@test "main: exits with usage when no host given" {
  run code_pull_main
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "main: rejects unknown options" {
  code_pull_check_ssh() { return 0; }

  run code_pull_main "host" "--bogus"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Unknown option"* ]]
}
