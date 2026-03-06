#!/usr/bin/env bash
# shellcheck shell=bash
# Discover and migrate git repos from a remote machine via SSH.
# Clean repos are cloned fresh; dirty repos (uncommitted changes/stashes) are
# transferred via rsync to preserve working tree state.
#
# Usage: scripts/code-pull.sh <source-hostname> [--dry-run] [--scan-only]
set -euo pipefail

# ---------------------------------------------------------------------------
# Source guard for testability (bats can source without executing main logic)
# ---------------------------------------------------------------------------
_CODE_PULL_SOURCED=1
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _CODE_PULL_SOURCED=0
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CODE_DIR="${CODE_DIR:-$HOME/code}"

RSYNC_OPTS=(
  -az
  --info=progress2
  --partial
  --partial-dir=.rsync-partial
  --human-readable
  --exclude='.git/objects/pack/*.tmp'
)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
code_pull_usage() {
  cat <<'EOF'
Usage: scripts/code-pull.sh <source-hostname> [--dry-run] [--scan-only]

Discover and migrate git repos from a remote machine.
Clean repos are cloned fresh; dirty repos are transferred via rsync.

Options:
  --dry-run     Preview the transfer without copying anything
  --scan-only   Discover repos and report status (no transfer)

Examples:
  make code-pull SOURCE=desktop        # migrate repos from 'desktop'
  scripts/code-pull.sh desktop         # direct invocation
  scripts/code-pull.sh desktop --scan-only
  scripts/code-pull.sh desktop --dry-run
EOF
}

code_pull_check_ssh() {
  local host="$1"
  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null; then
    echo "ERROR: Cannot connect to '$host' via SSH."
    echo "Ensure SSH key auth is configured and the host is reachable."
    return 1
  fi
}

code_pull_discover_repos() {
  # Discover git repos on the remote host under ~/code/.
  # Outputs one line per repo: <relative-path>
  local host="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" \
    'find ~/code -maxdepth 3 -name .git -type d 2>/dev/null | sed "s|^$HOME/code/||; s|/\.git$||" | sort'
}

code_pull_repo_status() {
  # Check if a remote repo is clean or dirty.
  # Output: "clean", "dirty", or "stashed"
  local host="$1" repo="$2"
  local result
  # shellcheck disable=SC2087
  result="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" bash -s -- "$repo" <<'REMOTE_SCRIPT'
repo="$1"
cd "$HOME/code/$repo" 2>/dev/null || { echo "missing"; exit; }
dirty=false
stashed=false
if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  dirty=true
fi
if [ "$(git stash list 2>/dev/null | wc -l)" -gt 0 ]; then
  stashed=true
fi
if [ "$dirty" = "true" ] || [ "$stashed" = "true" ]; then
  echo "dirty"
else
  echo "clean"
fi
REMOTE_SCRIPT
  )"
  echo "$result"
}

code_pull_get_remote_url() {
  # Get the origin remote URL from a remote repo (empty if none).
  local host="$1" repo="$2"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" \
    "cd ~/code/${repo} 2>/dev/null && git remote get-url origin 2>/dev/null" || true
}

code_pull_clone_repo() {
  # Clone a clean repo, preferring its origin remote URL.
  local host="$1" repo="$2" dry_run="$3"
  local remote_url dest
  dest="$CODE_DIR/$repo"

  if [[ -d "$dest" ]]; then
    echo "    Skipping (already exists locally)"
    echo "@@REPO_SKIP:${repo}@@"
    return 0
  fi

  remote_url="$(code_pull_get_remote_url "$host" "$repo")"

  if [[ "$dry_run" == "true" ]]; then
    if [[ -n "$remote_url" ]]; then
      echo "    Would clone from: $remote_url"
    else
      echo "    Would clone from: $host:~/code/$repo"
    fi
    echo "@@REPO_CLONE:${repo}:dry@@"
    return 0
  fi

  mkdir -p "$(dirname "$dest")"
  if [[ -n "$remote_url" ]]; then
    git clone "$remote_url" "$dest" 2>&1 | sed 's/^/    /'
  else
    git clone "$host:code/$repo" "$dest" 2>&1 | sed 's/^/    /'
  fi
  echo "@@REPO_CLONE:${repo}@@"
}

code_pull_rsync_repo() {
  # Transfer a dirty repo via rsync to preserve working tree state.
  local host="$1" repo="$2" dry_run="$3"
  local src="$host:code/$repo/"
  local dest="$CODE_DIR/$repo/"

  if [[ "$dry_run" == "true" ]]; then
    echo "    Would rsync from: $src"
    echo "@@REPO_RSYNC:${repo}:dry@@"
    return 0
  fi

  mkdir -p "$dest"
  rsync "${RSYNC_OPTS[@]}" "$src" "$dest" 2>&1 | sed 's/^/    /'
  echo "@@REPO_RSYNC:${repo}@@"
}

code_pull_main() {
  local source_host="${1:-}"
  local dry_run="false"
  local scan_only="false"

  if [[ -z "$source_host" ]]; then
    code_pull_usage
    exit 1
  fi

  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      --scan-only) scan_only="true"; shift ;;
      -h|--help) code_pull_usage; exit 0 ;;
      *) echo "Unknown option: $1"; code_pull_usage; exit 1 ;;
    esac
  done

  code_pull_check_ssh "$source_host"

  echo "Discovering repos on $source_host..."
  local repos
  repos="$(code_pull_discover_repos "$source_host")"

  if [[ -z "$repos" ]]; then
    echo "No git repos found under ~/code/ on $source_host."
    return 0
  fi

  local total cloned rsynced skipped
  total=0 cloned=0 rsynced=0 skipped=0

  # Classify repos
  declare -a clean_repos=() dirty_repos=()
  while IFS= read -r repo; do
    [[ -z "$repo" ]] && continue
    total=$((total + 1))
    local status
    status="$(code_pull_repo_status "$source_host" "$repo")"
    echo "@@SCAN:${repo}:${status}@@"

    if [[ "$status" == "clean" ]]; then
      clean_repos+=("$repo")
    else
      dirty_repos+=("$repo")
    fi
  done <<< "$repos"

  echo ""
  echo "Found $total repos: ${#clean_repos[@]} clean, ${#dirty_repos[@]} dirty"
  echo ""

  if [[ "$scan_only" == "true" ]]; then
    return 0
  fi

  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN — no files will be transferred ==="
    echo ""
  fi

  # Clone clean repos
  for repo in "${clean_repos[@]}"; do
    echo "=== Clone: $repo (clean) ==="
    code_pull_clone_repo "$source_host" "$repo" "$dry_run"
    cloned=$((cloned + 1))
    echo ""
  done

  # Rsync dirty repos
  for repo in "${dirty_repos[@]}"; do
    echo "=== Rsync: $repo (dirty) ==="
    code_pull_rsync_repo "$source_host" "$repo" "$dry_run"
    rsynced=$((rsynced + 1))
    echo ""
  done

  echo "@@SUMMARY:${total}:${cloned}:${rsynced}:${skipped}@@"
  if [[ "$dry_run" == "true" ]]; then
    echo "=== DRY RUN complete. No files were transferred. ==="
  else
    echo "=== Code migration from $source_host complete. ==="
    echo "    Cloned: $cloned  |  Rsynced: $rsynced  |  Total: $total"
  fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ "$_CODE_PULL_SOURCED" -eq 0 ]]; then
  code_pull_main "$@"
fi
