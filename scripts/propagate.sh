#!/usr/bin/env bash
# Workstation propagation: pull upstream changes and notify.
# Called by launchd (macOS) or systemd timer (Linux) on login.
set -euo pipefail

REPO_DIR="${WORKSTATION_REPO:-$HOME/.workstation}"
SENTINEL="$HOME/.workstation-no-propagate"
LOCK_DIR="$HOME/.local/run"
LOCK_FILE="$LOCK_DIR/workstation-propagate.lock"
STATUS_DIR="$HOME/.local/state"
STATUS_FILE="$STATUS_DIR/workstation-propagate-status"
LOG_DIR="$HOME/.local/log"
LOG_FILE="$LOG_DIR/workstation-propagate.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"; }

notify() {
    local title="$1" body="$2"
    if [[ "$(uname)" == "Darwin" ]]; then
        osascript -e "display notification \"$body\" with title \"$title\"" 2>/dev/null || true
    elif command -v notify-send &>/dev/null; then
        notify-send "$title" "$body" 2>/dev/null || true
    fi
}

# Ensure directories exist.
mkdir -p "$LOCK_DIR" "$STATUS_DIR" "$LOG_DIR"

# Sentinel: user has opted out.
if [[ -f "$SENTINEL" ]]; then
    log "Sentinel $SENTINEL exists — skipping propagation."
    exit 0
fi

# Repo must exist.
if [[ ! -d "$REPO_DIR/.git" ]]; then
    log "ERROR: $REPO_DIR is not a git repository."
    exit 1
fi

# Lock: only one propagation at a time.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "Another propagation is running — skipping."
    exit 0
fi

cd "$REPO_DIR"

log "Fetching origin..."
if ! git fetch origin main --quiet 2>>"$LOG_FILE"; then
    log "ERROR: git fetch failed (offline?)."
    echo "fetch-failed $(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit 0
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [[ "$LOCAL" == "$REMOTE" ]]; then
    log "Already up to date."
    echo "up-to-date $(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit 0
fi

# Attempt fast-forward only — never auto-merge.
if ! git pull --ff-only --quiet 2>>"$LOG_FILE"; then
    log "WARNING: branches have diverged — manual merge required."
    echo "diverged $(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    notify "Workstation: branches diverged" \
        "Run 'cd $REPO_DIR && git pull' to resolve."
    exit 0
fi

NEW_HEAD=$(git rev-parse --short HEAD)
COMMIT_COUNT=$(git rev-list "$LOCAL".."$REMOTE" --count)
log "Pulled $COMMIT_COUNT new commit(s), now at $NEW_HEAD."
echo "pulled $COMMIT_COUNT $NEW_HEAD $(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"

notify "Workstation updated" \
    "$COMMIT_COUNT new commit(s) pulled. Run 'make apply' when ready."
