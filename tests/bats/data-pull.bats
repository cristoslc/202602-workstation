#!/usr/bin/env bats

load helpers/setup

SCRIPT_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"

setup() {
  TEST_TEMP="$(mktemp -d)"
  export TEST_TEMP

  # Source the script (loads functions without executing main)
  source "$SCRIPT_DIR/scripts/data-pull.sh"
}

teardown() {
  rm -rf "$TEST_TEMP"
}

# --- Configuration ---

@test "USER_FOLDERS contains expected folders" {
  [[ " ${USER_FOLDERS[*]} " == *" Desktop "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Documents "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Downloads "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Movies "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Music "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Pictures "* ]]
  [[ " ${USER_FOLDERS[*]} " == *" Videos "* ]]
  [ "${#USER_FOLDERS[@]}" -eq 7 ]
}

@test "RSYNC_OPTS contains --info=progress2" {
  local opts="${RSYNC_OPTS[*]}"
  [[ "$opts" == *"--info=progress2"* ]]
}

@test "RSYNC_OPTS contains --partial" {
  local opts="${RSYNC_OPTS[*]}"
  [[ "$opts" == *"--partial"* ]]
}

@test "RSYNC_OPTS contains --delete" {
  local opts="${RSYNC_OPTS[*]}"
  [[ "$opts" == *"--delete"* ]]
}

# --- data_pull_usage ---

@test "usage: includes --scan-only option" {
  run data_pull_usage
  [ "$status" -eq 0 ]
  [[ "$output" == *"--scan-only"* ]]
}

@test "usage: includes --dry-run option" {
  run data_pull_usage
  [ "$status" -eq 0 ]
  [[ "$output" == *"--dry-run"* ]]
}

# --- data_pull_scan_sizes ---

@test "scan_sizes: emits @@SCAN:…@@ markers for each folder" {
  # Stub data_pull_scan_folder to return predictable sizes
  data_pull_scan_folder() {
    local folder="$2"
    case "$folder" in
      Desktop)   echo "1000" ;;
      Documents) echo "2000" ;;
      Downloads) echo "3000" ;;
      Movies)    echo "4000" ;;
      Music)     echo "5000" ;;
      Pictures)  echo "6000" ;;
      Videos)    echo "7000" ;;
    esac
  }

  run data_pull_scan_sizes "fakehost"
  [ "$status" -eq 0 ]
  [[ "$output" == *"@@SCAN:Desktop:1000@@"* ]]
  [[ "$output" == *"@@SCAN:Documents:2000@@"* ]]
  [[ "$output" == *"@@SCAN:Downloads:3000@@"* ]]
  [[ "$output" == *"@@SCAN:Videos:7000@@"* ]]
}

@test "scan_sizes: emits @@TOTAL:…@@ with correct sum" {
  data_pull_scan_folder() {
    local folder="$2"
    case "$folder" in
      Desktop)   echo "100" ;;
      Documents) echo "200" ;;
      Downloads) echo "300" ;;
      Movies)    echo "400" ;;
      Music)     echo "500" ;;
      Pictures)  echo "600" ;;
      Videos)    echo "700" ;;
    esac
  }

  run data_pull_scan_sizes "fakehost"
  [ "$status" -eq 0 ]
  [[ "$output" == *"@@TOTAL:2800@@"* ]]
}

# --- data_pull_sync_folder ---

@test "sync_folder: emits FOLDER_START and FOLDER_DONE markers" {
  # Stub rsync to succeed without doing anything
  rsync() { return 0; }
  export -f rsync

  export HOME="$TEST_TEMP/home"
  mkdir -p "$HOME"

  run data_pull_sync_folder "fakehost" "Desktop" "true"
  [ "$status" -eq 0 ]
  [[ "$output" == *"@@FOLDER_START:Desktop@@"* ]]
  [[ "$output" == *"@@FOLDER_DONE:Desktop@@"* ]]
  [[ "$output" == *"=== Syncing Desktop from fakehost ==="* ]]
}

@test "sync_folder: creates target directory" {
  rsync() { return 0; }
  export -f rsync

  export HOME="$TEST_TEMP/home"
  run data_pull_sync_folder "fakehost" "Documents" "false"
  [ "$status" -eq 0 ]
  [ -d "$TEST_TEMP/home/Documents" ]
}

# --- data_pull_main argument parsing ---

@test "main: exits with usage when no host given" {
  run data_pull_main
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "main: rejects unknown options" {
  # Stub SSH check to pass
  data_pull_check_ssh() { return 0; }

  run data_pull_main "host" "--bogus"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Unknown option"* ]]
}
