---
title: "SPEC-003: wsync Multi-Directory Support"
artifact: SPEC-003
status: Draft
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
linked-research:
  - SPIKE-006
  - SPIKE-008
linked-adrs:
  - ADR-006
depends-on:
  - SPEC-002
---

# SPEC-003: wsync Multi-Directory Support

## Problem Statement

The `wsync` script currently discovers git repos from a single directory (`$WSYNC_CODE_DIR`, default `~/code/`). SPEC-002 introduces a detection journal that records git repos found anywhere in Syncthing-managed folders (e.g., `~/Documents/HouseOps/`). These repos are excluded from Syncthing but have no Unison sync coverage — they exist only on the machine where they were detected. wsync must be extended to read the journal and provide branch-aware Unison sync for repos outside `~/code/`.

## External Behavior

### Inputs

- Detection journal: `~/.config/wsync/detected-repos` (written by SPEC-002's scanner)
- Existing config: `$WSYNC_CODE_DIR` (default `~/code/`)
- Optional config: `$WSYNC_EXTRA_DIRS` or `~/.config/wsync/extra-dirs` (manually specified additional directories)

### Outputs

- Unison sync of all discovered repos (both `~/code/` and journal entries) to hub with branch isolation
- Hub directory structure: `/srv/code-sync/<qualified-name>/<branch>/`
- Updated `wsync --status` output showing all synced repos with their source directory

### Preconditions

- SPEC-002 is implemented (detection journal exists and is populated)
- Unison and wsync are installed and configured
- Hub server is reachable via SSH

### Postconditions

- Every repo in the detection journal gets branch-aware Unison sync
- Repos from different source directories with the same basename are disambiguated on the hub
- `wsync --status` shows repos from all directories, not just `~/code/`

### Interfaces

| Interface | Direction | Description |
|-----------|-----------|-------------|
| `~/.config/wsync/detected-repos` | Input | Journal from SPEC-002 |
| `~/.config/wsync/extra-dirs` | Input | Optional manual directory list |
| `/srv/code-sync/<qualified-name>/<branch>/` | Output | Hub directory per repo per branch |
| `wsync --status` | Output | Status table including all repos |

## Acceptance Criteria

1. **Given** `~/Documents/HouseOps/` is in the detection journal, **when** `wsync` runs, **then** `HouseOps` is synced to the hub with branch isolation, identical to repos in `~/code/`.

2. **Given** both `~/code/myrepo` and `~/Documents/myrepo` exist, **when** `wsync` runs, **then** they are synced to distinct hub directories using qualified names (e.g., `code--myrepo` and `documents--myrepo`).

3. **Given** a repo is removed from the detection journal (`.git/` deleted), **when** `wsync` runs, **then** it is no longer synced, and `wsync --status` no longer lists it. Hub data is retained for manual cleanup.

4. **Given** `wsync --status` is run, **when** repos exist in both `~/code/` and the journal, **then** all repos are listed with their source directory and current branch.

5. **Given** `WSYNC_EXTRA_DIRS` is set to `/home/user/projects:/home/user/work`, **when** `wsync` discovers repos, **then** it scans those directories in addition to `$WSYNC_CODE_DIR` and the journal.

## Scope & Constraints

### In scope

- `wsync_discover_repos()` expansion to accept multiple directories
- Journal reading logic (parse `~/.config/wsync/detected-repos`)
- `WSYNC_EXTRA_DIRS` env var and/or config file support
- Qualified naming scheme for hub directories
- `wsync --status` update to show source directory
- Ansible variable for extra directories (`unison_extra_dirs`)

### Out of scope

- Detection of git repos (SPEC-002)
- `.stglobalignore` management (SPEC-002)
- Nested repo discovery (wsync remains one-level-deep within each directory)
- Hub cleanup of orphaned repo directories (manual for now)

## Implementation Approach

### 1. Qualified naming scheme

To avoid collisions when repos from different directories share a basename, use a qualified name on the hub:

- Repos from `$WSYNC_CODE_DIR` (`~/code/`): use basename as-is (e.g., `myrepo`) for backward compatibility
- Repos from other directories: prefix with the parent folder name, double-dash separated (e.g., `documents--HouseOps`, `pictures--photo-tools`)

### 2. wsync_discover_repos() expansion

Modify the function to:
1. Scan `$WSYNC_CODE_DIR` (existing behavior)
2. Read `~/.config/wsync/detected-repos` and scan each listed parent directory
3. Read `$WSYNC_EXTRA_DIRS` (colon-separated) or `~/.config/wsync/extra-dirs` (one per line)
4. Deduplicate repos that appear in multiple sources
5. Return repo list with qualified names

### 3. Status output update

Update `wsync --status` table to include a "Source" column showing where each repo was discovered (e.g., `~/code/`, `~/Documents/`, `journal`).

### 4. Ansible integration

Add `unison_extra_dirs: []` to `shared/roles/unison/defaults/main.yml`. When set, write to `~/.config/wsync/extra-dirs` during role execution.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | 871b26c | Initial creation |
