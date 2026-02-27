#!/usr/bin/env bash
# shellcheck shell=bash
# Bulk-copy user data folders from a remote machine via rsync over SSH.
# Usage: scripts/data-pull.sh <source-hostname> [--dry-run] [--scan-only]
set -euo pipefail

# ---------------------------------------------------------------------------
# Source guard for testability (bats can source without executing main logic)
# ---------------------------------------------------------------------------
_DATA_PULL_SOURCED=1
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _DATA_PULL_SOURCED=0
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
USER_FOLDERS=(Desktop Documents Downloads Movies Music Pictures Videos)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXCLUDE_FILE="${SCRIPT_DIR}/data-pull-excludes.txt"

RSYNC_OPTS=(
  -az                   # archive, compress
  --info=progress2      # overall transfer progress (% / speed / ETA)
  --partial             # resume interrupted transfers
  --human-readable      # human-readable sizes
  --exclude-from="$EXCLUDE_FILE"
)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
data_pull_usage() {
  cat <<'EOF'
Usage: scripts/data-pull.sh <source-hostname> [--dry-run] [--scan-only]

Bulk-copy user data folders from a remote machine to this one via rsync/SSH.

Folders synced: Desktop, Documents, Downloads, Movies, Music, Pictures, Videos

Options:
  --dry-run     Preview the transfer without copying anything (rsync -n)
  --scan-only   Report remote folder sizes and exit (no transfer)

Examples:
  make data-pull SOURCE=desktop        # copy from 'desktop'
  make data-pull-dry SOURCE=desktop    # preview what would be copied
  scripts/data-pull.sh desktop         # direct invocation
  scripts/data-pull.sh desktop --dry-run
  scripts/data-pull.sh desktop --scan-only
EOF
}

data_pull_check_ssh() {
  local host="$1"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null; then
    echo "ERROR: Cannot connect to '$host' via SSH."
    echo "Ensure SSH key auth is configured and the host is reachable."
    return 1
  fi
}

data_pull_folder_exists() {
  # Check if a folder exists on the remote host.
  local host="$1" folder="$2"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" \
    "test -d ~/$folder" 2>/dev/null
}

data_pull_scan_folder() {
  # Get the total file size of a remote folder (approx bytes) via SSH du.
  # Uses du -sk (kilobytes) for cross-platform compat (BSD + GNU).
  local host="$1" folder="$2"
  local kb
  kb="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" \
    "du -sk ~/$folder/ 2>/dev/null | cut -f1" 2>/dev/null)" || kb=0
  [[ -z "$kb" ]] && kb=0
  echo $(( kb * 1024 ))
}

data_pull_scan_sizes() {
  # Print a structured size summary for each folder on the remote host.
  # Output lines: @@SCAN:<folder>:<bytes>@@
  # Final line:   @@TOTAL:<total_bytes>@@
  local host="$1"
  local total=0

  echo "Scanning remote folder sizes on $host..."

  for folder in "${USER_FOLDERS[@]}"; do
    local bytes
    bytes="$(data_pull_scan_folder "$host" "$folder")"
    echo "@@SCAN:${folder}:${bytes}@@"
    total=$((total + bytes))
  done

  echo "@@TOTAL:${total}@@"
}

data_pull_sync_folder() {
  local host="$1" folder="$2" dry_run="${3:-false}"
  local src="$host:~/$folder/"
  local dst="$HOME/$folder/"

  echo ""
  if ! data_pull_folder_exists "$host" "$folder"; then
    echo "=== Skipping $folder (not found on $host) ==="
    return 0
  fi

  local opts=("${RSYNC_OPTS[@]}")
  if [[ "$dry_run" == "true" ]]; then
    opts+=(--dry-run)
  fi

  echo "@@FOLDER_START:${folder}@@"
  echo "=== Syncing $folder from $host ==="
  mkdir -p "$dst"
  rsync "${opts[@]}" "$src" "$dst"
  echo "@@FOLDER_DONE:${folder}@@"
}

data_pull_local_folder_size() {
  # Get the local size of a folder (approx bytes via du -sk).
  local folder="$1"
  local dir="$HOME/$folder"
  if [[ ! -d "$dir" ]]; then
    echo "0"
    return
  fi
  local kb
  kb="$(du -sk "$dir" 2>/dev/null | cut -f1)" || kb=0
  [[ -z "$kb" ]] && kb=0
  echo $(( kb * 1024 ))
}

data_pull_verify() {
  # Compare local folder sizes against remote sizes after migration.
  # Emits @@VERIFY:<folder>:<local_bytes>:<remote_bytes>@@ markers.
  local host="$1"

  echo ""
  echo "@@VERIFY_START@@"
  echo "Verifying migrated data..."

  for folder in "${USER_FOLDERS[@]}"; do
    local remote_bytes local_bytes
    remote_bytes="$(data_pull_scan_folder "$host" "$folder")"
    local_bytes="$(data_pull_local_folder_size "$folder")"
    echo "@@VERIFY:${folder}:${local_bytes}:${remote_bytes}@@"
  done

  echo "@@VERIFY_DONE@@"
}

data_pull_main() {
  local source_host="${1:-}"
  local dry_run="false"
  local scan_only="false"

  if [[ -z "$source_host" ]]; then
    data_pull_usage
    exit 1
  fi

  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      --scan-only) scan_only="true"; shift ;;
      -h|--help) data_pull_usage; exit 0 ;;
      *) echo "Unknown option: $1"; data_pull_usage; exit 1 ;;
    esac
  done

  data_pull_check_ssh "$source_host"

  if [[ "$scan_only" == "true" ]]; then
    data_pull_scan_sizes "$source_host"
    return 0
  fi

  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN — no files will be copied ==="
  fi

  echo "Source: $source_host"
  echo "Target: $HOME"
  echo "Folders: ${USER_FOLDERS[*]}"
  echo ""

  # Scan remote sizes for progress tracking
  data_pull_scan_sizes "$source_host"
  echo ""

  for folder in "${USER_FOLDERS[@]}"; do
    data_pull_sync_folder "$source_host" "$folder" "$dry_run"
  done

  echo ""
  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN complete. No files were copied. ==="
  else
    # Verify local vs remote sizes
    data_pull_verify "$source_host"
    echo ""
    echo "=== Data pull from $source_host complete. ==="
  fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ "$_DATA_PULL_SOURCED" -eq 0 ]]; then
  data_pull_main "$@"
fi
