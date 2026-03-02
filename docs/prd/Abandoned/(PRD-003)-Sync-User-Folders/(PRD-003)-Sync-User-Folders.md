---
title: "PRD-003: Sync User Folders"
artifact: PRD-003
status: Abandoned
author: cristos
created: 2026-02-26
last-updated: 2026-03-01
migrated-to: EPIC-002
---

# PRD-003: Sync User Folders

> **Migrated:** This PRD has been superseded by [EPIC-002](../../../epic/(EPIC-002)-Sync-User-Folders/(EPIC-002)-Sync-User-Folders.md). This file is retained for history.

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-02-26 | 28b0c6d | Initial creation (originally PRD-002, renumbered at 4fbccef) |
| Abandoned | 2026-03-01 | dc0f8d9 | Migrated to EPIC-002 |

---

## Problem

After `make bootstrap` provisions a workstation, user data folders (Documents, Pictures, Music, Videos, Downloads) and code repository working trees remain stranded on the source machine. Two pain points:

1. **One-time migration** — No automated way to bulk-copy user data from an existing machine to a freshly provisioned one. Users resort to ad-hoc rsync commands or USB drives.

2. **Ongoing sync** — No mechanism keeps user folders and code working trees in sync across 2-3 workstations (desktop, laptop, possibly macOS). Switching machines means either committing WIP code (noisy, loses staging state) or manually copying files.

Code repositories pose a special challenge: general file-sync tools (Syncthing, Dropbox) either corrupt `.git/` internals or garble working trees when machines are on different branches (see [syncthing-git-repos.md](../../../research/Active/(SPIKE-006)-Sync-User-Folders/syncthing-git-repos.md)).

This contradicts the workstation goal of single-command provisioning that produces a fully usable machine.

## Goal

After bootstrap + a one-time migration step, user data folders stay in continuous sync across all workstations. Code repositories sync working tree state (including uncommitted changes) with branch-level isolation. Switching machines requires no manual intervention beyond waking the target device.

## Scope

### In scope

- **One-time data migration** via rsync (`make data-pull SOURCE=<hostname>`) for bulk-copying Documents, Pictures, Music, Videos, Downloads from an existing machine to a new one
- **Ongoing user data sync** via Syncthing in a hub-and-spoke topology — home server as always-on hub, workstations as spokes, all bidirectional (Send & Receive)
- **Ongoing code sync** via Unison with branch-aware directory isolation — working trees (excluding `.git/`) route through the hub server keyed by `<repo>/<branch>`
- **Ansible roles** for installing and configuring Syncthing (all platforms) and Unison (all platforms + hub server)
- **`wsync` wrapper script** for on-demand and timer-driven code sync (systemd timer on Linux, launchd agent on macOS)
- **Wake-from-suspend triggers** to ensure machines catch up immediately after sleep (systemd `Persistent=true`, macOS `sleepwatcher` or interval)
- **Unison profile management** — base profile (`code-sync.prf`) deployed via Ansible, dynamic roots per repo+branch
- **Hub server directory setup** (`/srv/code-sync/` for Unison, Syncthing data directory for user folders)
- **.stignore deployment** for Syncthing folders (exclude `.git/`, build artifacts, OS metadata)

### Out of scope

- **Dotfiles** — managed by GNU Stow, not file sync
- **System configuration** — managed by Ansible roles
- **Secrets** — managed by SOPS/age
- **Offsite / cloud backup** — separate concern (rclone + crypt or restic); may be a future PRD
- **Nextcloud / groupware** — calendar, contacts, and office are separate from file sync
- **Seafile evaluation** — research complete but not selected for initial implementation; Syncthing chosen for simplicity (no server-side application stack)
- **Syncthing git repo sync** — explicitly rejected per research (corruption risk)
- **Forgejo replacement** — Forgejo remains for committed history, CI/CD, and code review; Unison handles only working-state transfer

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Syncthing conflict on user data files | File renamed to `.sync-conflict-*`, user must resolve manually | Hub-and-spoke topology serializes changes, narrowing conflict window to seconds on LAN. User works on one machine at a time (typical). Enable Staggered file versioning for recovery. |
| Unison OCaml 5 silent data corruption | Critical — corrupted file sync without detection | Pin Unison to pre-built binaries compiled with OCaml 4.14 (Homebrew cask on macOS, GitHub release on Linux). Verify OCaml version in Ansible task. |
| Unison version mismatch across machines | Sync fails with wire protocol error | Pin Unison 2.53.x on all machines and hub via Ansible. Version check in `wsync` wrapper. |
| Hub server unavailable (power loss, network) | No syncing between any devices until hub returns | Fall back to `git push/pull` for committed code. Uncommitted work stays local. User data sync resumes automatically when hub reconnects. |
| Simultaneous edits on same branch (code) | Unison conflict; one version wins or sync skips file | Sequential workflow discipline (work on one machine at a time). `prefer = newer` auto-resolves. Unison backup preserves losing version. |
| Case sensitivity across macOS APFS and Linux ext4 | Persistent `.case-conflict-*` files in Syncthing | Enable `caseSensitiveFS` on macOS Syncthing. Avoid case-only renames. |
| Stale branch directories accumulate on hub | Disk usage grows unbounded | Periodic pruning cron (remove directories not modified in 30+ days). |
| macOS launchd lacks native wake event | Up to 5-minute delay before code sync after wake | Install `sleepwatcher` via Homebrew for immediate wake trigger; or accept 5-minute max latency. |

## Research

| ID | Question | Status | Blocks |
|----|----------|--------|--------|
| sync-user-folders | What tools and topologies work for migrating and syncing user data folders and code repos across 2-3 workstations? | Active | Implementation |
| syncthing-hub-spoke | How does Syncthing perform in a hub-and-spoke topology for user data sync? What are the conflict mechanics and folder-type strategies? | Active (within sync-user-folders) | Syncthing role design |
| syncthing-git-repos | Can Syncthing safely sync git repositories? | Active (within sync-user-folders) | Code sync approach decision (answered: no) |
| unison-code-sync | How to sync code working trees with branch isolation, excluding `.git/`? | Active (within sync-user-folders) | `wsync` implementation |

## Success Criteria

1. `make data-pull SOURCE=<hostname>` bulk-copies Documents, Pictures, Music, Videos, and Downloads from the source machine to the local machine over SSH, preserving timestamps and permissions. A dry-run mode (`make data-pull-dry SOURCE=<hostname>`) previews the transfer.
2. Syncthing runs on all provisioned workstations and the hub server after `make apply`. User data folders (Documents, Pictures, Music, Videos, Downloads) are configured as shared folders in a hub-and-spoke topology with the home server as hub.
3. A file saved to `~/Documents/` on workstation A appears on workstation B within 60 seconds when both are connected to the hub on LAN.
4. `.git/` directories are excluded from Syncthing sync via deployed `.stignore` patterns.
5. `wsync` syncs all configured code repos' working trees to the hub, keyed by `<repo>/<branch>`. Running `wsync` on workstation A followed by `wsync` on workstation B results in identical working trees for repos on the same branch.
6. The systemd timer (Linux) and launchd agent (macOS) run `wsync` every 5 minutes and on wake from suspend. No manual intervention needed for routine machine switching.
7. Branch switching on one machine does not affect the other machine's working tree. Each branch syncs to an isolated server-side directory.
8. Uncommitted changes, untracked files, and staged file contents (via working tree copy) transfer between machines through `wsync`.
9. Unison version is pinned to 2.53.x across all machines and the hub. Ansible role verifies OCaml 4.14 compilation (not OCaml 5).
10. Syncthing Staggered file versioning is enabled on the hub for all shared folders.
