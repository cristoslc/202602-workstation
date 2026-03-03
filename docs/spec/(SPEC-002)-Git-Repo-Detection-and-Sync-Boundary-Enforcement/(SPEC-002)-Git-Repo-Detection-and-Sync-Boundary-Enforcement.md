---
title: "SPEC-002: Git Repo Detection and Sync Boundary Enforcement"
artifact: SPEC-002
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
linked-research:
  - SPIKE-006
  - SPIKE-008
linked-adrs:
  - ADR-006
depends-on: []
---

# SPEC-002: Git Repo Detection and Sync Boundary Enforcement

## Problem Statement

EPIC-002's sync architecture draws a hard boundary between Syncthing (user data) and Unison (code repos), but the boundary is enforced by convention ("put code in `~/code/`"), not by the tools. Git repos in Syncthing-managed folders have their working tree files synced across machines, causing branch garbling when machines are on different branches. The current `.stignore` excludes `.git/` but not the parent directory or working tree.

This spec implements ADR-006: a detection journal with real-time filesystem watching and `.stglobalignore`-based fleet-wide propagation of exclusion patterns.

## External Behavior

### Inputs

- Syncthing-managed folders: `~/Documents/`, `~/Pictures/`, `~/Music/`, `~/Videos/`, `~/Downloads/` (from `syncthing_user_folders` Ansible variable)
- Filesystem events: `.git/` directory creation, `.stglobalignore` file modification
- Syncthing REST API: `GET/POST /rest/db/ignores`, `POST /rest/db/scan` (requires API key from `config.xml`)

### Outputs

- **Detection journal:** `~/.config/wsync/detected-repos` — one line per detected repo, with path and metadata
- **`.stglobalignore` files:** One per Syncthing folder (e.g., `~/Documents/.stglobalignore`), containing relative paths of detected git repo directories
- **Syncthing state:** `.stignore` patterns updated via REST API for immediate local effect

### Preconditions

- Syncthing role is installed and configured (spoke or hub)
- `fswatch` is installed (`brew install fswatch` on macOS, `apt install fswatch` on Linux)
- Syncthing API key is readable from `~/.config/syncthing/config.xml` (or platform equivalent)

### Postconditions

- Every git repo in a Syncthing-managed folder is detected and excluded from Syncthing sync
- Exclusion patterns propagate to all devices in the fleet via `.stglobalignore`
- Detected repos are recorded in the journal for wsync consumption (SPEC-003)
- The scanner runs before Syncthing starts (boot) and before Syncthing reconnects (wake)

### Interfaces

| Interface | Direction | Description |
|-----------|-----------|-------------|
| `~/.config/wsync/detected-repos` | Output | Journal consumed by wsync (SPEC-003) |
| `~/Documents/.stglobalignore` (etc.) | Output | Synced by Syncthing to all devices |
| `POST /rest/db/ignores` | Output | Local Syncthing ignore update |
| `POST /rest/db/scan` | Output | Force rescan after `.stglobalignore` change from another device |
| FSEvents / inotify (via fswatch) | Input | Filesystem events for `.git/` and `.stglobalignore` |

## Acceptance Criteria

1. **Given** a git repo exists in `~/Documents/HouseOps/` at boot, **when** the machine boots, **then** `HouseOps` appears in `~/Documents/.stglobalignore` and Syncthing excludes it before syncing any files from that directory.

2. **Given** the system is running, **when** a user runs `git clone <url> ~/Documents/new-project`, **then** `new-project` is added to `~/Documents/.stglobalignore` and the Syncthing REST API is called to update ignores within the same FSEvents/inotify event batch.

3. **Given** Machine A detects a new repo, **when** Machine A writes to `.stglobalignore`, **then** the file syncs to Machine B via Syncthing, and Machine B's scanner triggers a `POST /rest/db/scan` to apply the new pattern.

4. **Given** the machine wakes from sleep, **when** the resume hook fires, **then** the scanner runs before Syncthing restarts, updating `.stglobalignore` with any repos created while awake.

5. **Given** the scanner detects repos, **when** it writes to `.stglobalignore`, **then** it preserves any entries written by other machines (merge, not overwrite).

6. **Given** the Hub server receives a `.stglobalignore` update via sync, **when** the Hub's Syncthing rescans, **then** the Hub stops relaying excluded directories to other spokes.

7. **Given** `make verify` is run, **when** unprotected git repos exist in Syncthing folders, **then** a warning is printed listing the unprotected repos.

## Scope & Constraints

### In scope

- Scanner script (`git-repo-scanner`)
- Detection journal format and write logic
- `.stglobalignore` write logic (per Syncthing folder, merge-safe)
- fswatch daemon (systemd service + launchd agent)
- Boot integration (systemd oneshot, launchd dependency)
- Wake integration (modify `syncthing-resume.sh`, macOS equivalent)
- `.stignore` Ansible template update (`#include .stglobalignore`)
- Hub `.stignore` update (add `#include .stglobalignore`)
- Syncthing REST API integration
- `make verify` safety net target
- fswatch installation via Ansible (both platforms)

### Out of scope

- wsync multi-directory support (SPEC-003)
- Unison profile changes (SPEC-003)
- JOURNEY-004 documentation (separate artifact)
- Syncthing #7096 upstream fix (workaround is in scope)

## Implementation Approach

### 1. `.stignore` template update

Update `shared/roles/syncthing/files/stignore` to append `#include .stglobalignore`. Update `shared/roles/syncthing-hub/` similarly. This is the foundation — all other components depend on Syncthing reading `.stglobalignore`.

### 2. Scanner script

Create `scripts/git-repo-scanner` (bash):
- Accepts a list of directories to scan (from Syncthing config or hardcoded)
- Runs `find <dir> -name .git -type d -prune` for each directory
- Computes relative path of each repo's parent within the Syncthing folder
- Merges entries into `<folder>/.stglobalignore` (read existing, add new, write back)
- Writes absolute paths to `~/.config/wsync/detected-repos` (journal)
- Calls `POST /rest/db/ignores` for immediate local Syncthing update
- Logs all detections

### 3. fswatch daemon

Create a persistent service that watches Syncthing-managed folders:
- Watch event 1: `.git/` directory creation anywhere in the tree → run scanner for that folder
- Watch event 2: `.stglobalignore` modification (from Syncthing sync) → call `POST /rest/db/scan` to force rescan
- Deployed as systemd user service (Linux) and launchd agent (macOS)

### 4. Boot/wake integration

- **Linux boot:** systemd oneshot service `git-repo-scanner.service` with `Before=syncthing@%i.service`
- **Linux wake:** modify `syncthing-resume.sh` to run scanner before Syncthing restart
- **macOS boot:** launchd agent with dependency on scanner completing before Syncthing agent
- **macOS wake:** scanner triggered by wake event (sleepwatcher or launchd KeepAlive pattern)

### 5. Ansible role

Create `shared/roles/git-repo-scanner/` with:
- `tasks/main.yml` — orchestration
- `tasks/debian.yml` — install fswatch, deploy systemd units
- `tasks/darwin.yml` — install fswatch (Homebrew), deploy launchd agents
- `files/git-repo-scanner` — the scanner script
- `files/git-repo-scanner.service` — systemd oneshot
- `files/git-repo-scanner-watch.service` — systemd fswatch daemon
- `files/com.workstation.git-repo-scanner.plist` — launchd agent

### 6. `make verify` target

Add a Makefile target that runs the scanner in dry-run mode, reporting any git repos in Syncthing folders that are not yet in `.stglobalignore`.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | 871b26c | Initial creation |
| Implemented | 2026-03-03 | d18c058 | Implementation complete |
