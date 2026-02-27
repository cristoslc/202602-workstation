#!/usr/bin/env bash
# shellcheck shell=bash
# Bulk-copy user data folders from a remote machine via rsync over SSH.
# Usage: scripts/data-pull.sh <source-hostname> [--dry-run]
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
  -avz                  # archive, verbose, compress
  --progress            # per-file progress
  --partial             # resume interrupted transfers
  --human-readable      # human-readable sizes
  --exclude-from="$EXCLUDE_FILE"
)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
data_pull_usage() {
  cat <<'EOF'
Usage: scripts/data-pull.sh <source-hostname> [--dry-run]

Bulk-copy user data folders from a remote machine to this one via rsync/SSH.

Folders synced: Desktop, Documents, Downloads, Movies, Music, Pictures, Videos

Options:
  --dry-run   Preview the transfer without copying anything (rsync -n)

Examples:
  make data-pull SOURCE=desktop        # copy from 'desktop'
  make data-pull-dry SOURCE=desktop    # preview what would be copied
  scripts/data-pull.sh desktop         # direct invocation
  scripts/data-pull.sh desktop --dry-run
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

data_pull_sync_folder() {
  local host="$1" folder="$2" dry_run="${3:-false}"
  local src="$host:~/$folder/"
  local dst="$HOME/$folder/"

  local opts=("${RSYNC_OPTS[@]}")
  if [[ "$dry_run" == "true" ]]; then
    opts+=(--dry-run)
  fi

  echo ""
  echo "=== Syncing $folder from $host ==="
  mkdir -p "$dst"
  rsync "${opts[@]}" "$src" "$dst"
}

data_pull_main() {
  local source_host="${1:-}"
  local dry_run="false"

  if [[ -z "$source_host" ]]; then
    data_pull_usage
    exit 1
  fi

  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      -h|--help) data_pull_usage; exit 0 ;;
      *) echo "Unknown option: $1"; data_pull_usage; exit 1 ;;
    esac
  done

  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN — no files will be copied ==="
  fi

  echo "Source: $source_host"
  echo "Target: $HOME"
  echo "Folders: ${USER_FOLDERS[*]}"
  echo ""

  data_pull_check_ssh "$source_host"

  for folder in "${USER_FOLDERS[@]}"; do
    data_pull_sync_folder "$source_host" "$folder" "$dry_run"
  done

  echo ""
  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN complete. No files were copied. ==="
  else
    echo "=== Data pull from $source_host complete. ==="
  fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ "$_DATA_PULL_SOURCED" -eq 0 ]]; then
  data_pull_main "$@"
fi
