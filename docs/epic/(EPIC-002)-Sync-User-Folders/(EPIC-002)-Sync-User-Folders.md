---
title: "EPIC-002: Sync User Folders"
artifact: EPIC-002
status: Active
author: cristos
created: 2026-03-01
last-updated: 2026-03-03
parent-vision: VISION-001
success-criteria:
  - "One-time data migration via `make data-pull SOURCE=<host>` works across macOS and Linux"
  - "Syncthing hub-and-spoke keeps user data folders in continuous sync"
  - "Unison syncs code working trees (including uncommitted changes) with branch isolation"
  - "Wake-from-suspend triggers catch up automatically"
  - "Zero manual sync configuration after bootstrap"
---

# EPIC-002: Sync User Folders

## Goal / Objective

After bootstrap and a one-time migration step, user data folders (Documents, Pictures, Music, Videos, Downloads) stay in continuous sync across all workstations via Syncthing. Code repositories sync working tree state (including uncommitted changes) with branch-level isolation via Unison. Switching machines requires no manual intervention beyond waking the target device.

## Scope Boundaries

### In scope

- One-time data migration via rsync (`make data-pull SOURCE=<hostname>`)
- Ongoing user data sync via Syncthing (hub-and-spoke topology)
- Ongoing code sync via Unison (branch-aware directory isolation, `.git/` excluded)
- Ansible roles for Syncthing and Unison (all platforms + hub server)
- `wsync` wrapper script + timer-driven sync (systemd/launchd)
- Wake-from-suspend triggers
- `.stignore` deployment for Syncthing folders

### Out of scope

- Dotfiles (managed by GNU Stow)
- Secrets (managed by SOPS/age)
- Offsite/cloud backup (separate concern — EPIC-001)
- Syncthing git repo sync (explicitly rejected per SPIKE-006 research)
- Nextcloud/groupware (calendar, contacts, office are separate)

## Child Specs

_To be created. Likely decomposition:_
- Data migration pipeline (rsync pull)
- Syncthing hub-and-spoke configuration
- Unison code sync with branch isolation
- wsync wrapper and scheduled triggers

## Key Dependencies

- [SPIKE-006](../../research/Complete/(SPIKE-006)-Sync-User-Folders/(SPIKE-006)-Sync-User-Folders.md) — Sync User Folders research (Complete)
- Hub server availability (Syncthing relay, Unison rendezvous)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Syncthing conflict on user data | `.sync-conflict-*` files require manual resolution | Hub-and-spoke serializes; enable staggered versioning |
| Unison OCaml 5 data corruption | Silent corruption | Pin Unison to OCaml 4.14 builds; verify in Ansible |
| Unison version mismatch | Sync fails | Pin version across all machines via Ansible |
| Hub server unavailable | No syncing until hub returns | Fall back to `git push/pull`; auto-resume on reconnect |

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Vision | [VISION-001](../../vision/(VISION-001)-Workstation-as-Code/(VISION-001)-Workstation-as-Code.md) | Workstation as Code |
| Spike | [SPIKE-006](../../research/Complete/(SPIKE-006)-Sync-User-Folders/(SPIKE-006)-Sync-User-Folders.md) | Sync User Folders |
| Legacy | [PRD-003](../../prd/Abandoned/(PRD-003)-Sync-User-Folders/(PRD-003)-Sync-User-Folders.md) | Sync User Folders (migrated from PRD) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-01 | 028b2ad | Migrated from PRD-003 |
| Active | 2026-03-03 | 42cf76d | SPIKE-006 Complete; beginning implementation |
