---
title: "ADR-006: Git Repo Detection Journal with Sync Boundary Enforcement"
artifact: ADR-006
status: Adopted
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
decision-date: 2026-03-03
linked-epics:
  - EPIC-002
linked-research:
  - SPIKE-006
  - SPIKE-008
---

# ADR-006: Git Repo Detection Journal with Sync Boundary Enforcement

## Context

EPIC-002's sync architecture uses two tools: Syncthing for user data folders (`~/Documents/`, `~/Pictures/`, etc.) and Unison for code repos (`~/code/`). The boundary between them is enforced by convention — "put code in `~/code/`" — but in practice, git repos exist outside that convention (e.g., `~/Documents/HouseOps/`).

The current `.stignore` excludes `.git/` directories from Syncthing but does NOT exclude the parent directory or its working tree files. When two machines are on different branches, Syncthing silently garbles the working tree by merging files from both branches. This is an active problem, not a theoretical one.

SPIKE-006 established that Syncthing cannot safely sync git repos due to branch isolation requirements — Unison solves this via branch-keyed directories on the hub (`/srv/code-sync/<repo>/<branch>/`). SPIKE-008 evaluated five approaches and concluded that the two-tool architecture is correct but the boundary needs active enforcement, not passive convention.

The key architectural questions resolved:

1. **Why not Unison for everything?** Unison cannot replace Syncthing for user data: 30-minute initial scan for 100K files, 600MB RAM, no native macOS file watching, no conflict versioning, no NAT traversal.
2. **Why not Syncthing for code repos?** Branch isolation is non-negotiable. Syncthing has no concept of branches; it sees file changes as independent and merges working trees across branches. Syncthing maintainers explicitly rejected VCS-aware ignore features (GitHub issue #7215).
3. **Why not polling every N minutes?** Syncthing detects filesystem changes in milliseconds via FSEvents/inotify. Any polling interval loses the race — a new repo's working tree gets synced before the scanner detects it.

## Decision

Implement a **detection journal** as the single source of truth for git repos found in Syncthing-managed folders. The journal feeds both Syncthing (exclusion) and wsync/Unison (inclusion).

### Detection journal

A file at `~/.config/wsync/detected-repos` records every git repo found in Syncthing territory, with metadata (path, detection timestamp, machine). Both downstream consumers read from this journal:

- **Syncthing:** Journal entries are translated to `.stignore` patterns via `POST /rest/db/ignores` (atomic update, triggers immediate rescan).
- **wsync:** Journal entries are added to the repo discovery list, giving repos outside `~/code/` the same branch-aware Unison sync treatment.

### Boot sequence: delayed Syncthing start

The scanner runs as a oneshot service **before** Syncthing starts:

- **Linux:** systemd ordering with `Before=syncthing@.service`
- **macOS:** launchd dependency ordering

On boot, the scanner does a `find` sweep of all Syncthing-managed folders, writes the journal, and updates `.stignore`. Syncthing then starts with correct ignores already in place. This provides **zero race window for existing repos** — the most dangerous case.

### Runtime: real-time filesystem watching

After boot, a persistent `fswatch` process monitors Syncthing-managed folders for `.git/` directory creation. On detection, the scanner immediately updates the journal and `.stignore`. This uses the **same technology Syncthing does** (FSEvents on macOS, inotify on Linux), matching its detection speed and reducing the race window to milliseconds.

### Unison is retained for code repos

Branch isolation remains non-negotiable for git repos. Unison syncs working tree files (excluding `.git/`) to branch-keyed directories on the hub. wsync is extended with `WSYNC_EXTRA_DIRS` support to handle repos discovered by the journal, not just those in `~/code/`.

### Syncthing remains continuous for user data

Syncthing continues running as a continuous daemon after the boot-delay scan. Its strengths — real-time filesystem watching, staggered versioning, NAT traversal, multi-device mesh — are the right fit for user data. The on-demand model was considered and rejected because it sacrifices the "save and forget" UX.

## Alternatives Considered

### Approach A: Periodic polling scanner (5-minute interval)

Piggyback on wsync's existing 5-minute timer to scan for `.git/` directories.

**Rejected because:** Syncthing detects filesystem changes in milliseconds. A 5-minute polling interval always loses the race — a new repo's working tree gets synced (and potentially garbled) before the scanner runs. Even 5-second polling is too slow.

### Approach B: Syncthing event API hook

Use Syncthing's `LocalChangeDetected` / `RemoteChangeDetected` events to detect `.git/` creation.

**Rejected because:** These events fire *after* the sync operation. The first sync of working tree files has already happened before any event is emitted. The damage occurs before detection.

### Approach C: Unison for everything (replace Syncthing)

Eliminate the two-tool boundary by using Unison for all sync.

**Rejected because:** Unison is not viable for user data at scale. Initial scan of 100K files takes ~30 minutes. Memory usage ~600MB. No native continuous watching on macOS (requires third-party `unison-fsmonitor` adapter). No conflict versioning (Syncthing's staggered `.stversions/` is superior). Strictly pairwise topology (2 roots per profile). No NAT traversal.

### Approach E: Convention + guardrails (no automation)

Document the "put code in `~/code/`" convention, add `make verify` warnings, add a shell alias that warns on `git init` outside `~/code/`.

**Rejected because:** Fails three of four go/no-go criteria (Detection, Protection, UX). Warnings don't prevent damage. Users shouldn't need to think about sync tools when choosing where to put a project.

### On-demand Syncthing (run scanner before each sync cycle)

Make Syncthing timer-based instead of continuous, with the scanner guaranteed to run first.

**Rejected because:** This sacrifices Syncthing's core value — continuous, real-time, fire-and-forget sync of user data. If Syncthing is on-demand, files don't sync until the timer fires. The delayed-start + fswatch approach achieves the same protection without degrading user data sync.

## Consequences

### Positive

- **Git repos can live anywhere.** Users don't need to think about sync tool boundaries. The system detects and routes automatically.
- **Zero race window at boot** for existing repos. The most dangerous case (reconnecting machines on different branches) is fully protected.
- **Near-zero race window at runtime.** fswatch matches Syncthing's detection speed; the millisecond window during fresh clones causes no practical damage (same branch on both machines).
- **Single source of truth.** The journal provides auditability and a single debugging surface for both Syncthing exclusion and Unison inclusion.
- **Minimal architectural change.** Both tools continue doing what they do best. The journal and scanner are additive, not disruptive.

### Accepted downsides

- **New daemon.** The fswatch scanner is a new long-running process that must be managed (systemd/launchd), monitored, and kept running.
- **Syncthing boot delay.** The scanner must complete before Syncthing starts. For a typical home directory, `find -name .git` takes < 1 second, but this adds a hard dependency to the boot sequence.
- **Already-synced files are not cleaned up.** Syncthing leaves already-synced files in place when a new ignore pattern is added. Repos that were already damaged by Syncthing before the scanner was deployed require manual `git checkout .` recovery. This is a one-time migration concern, not ongoing.
- **EPIC-002 regression.** Implementation requires EPIC-002 to regress from Testing to Active for the scanner service and wsync expansion work.

### Follow-on work

- **JOURNEY-004 (Daily Multi-Machine Workflow):** New journey documenting the steady-state experience: "Put files anywhere. The system detects git repos and routes them to the right sync tool."
- **JOURNEY-003 update:** Add guidance for repos outside `~/code/` during machine migration.
- **wsync expansion:** Add `WSYNC_EXTRA_DIRS` support and qualified naming for repos outside `~/code/`.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Adopted | 2026-03-03 | c950e4b | Decision from SPIKE-008 research; skip Draft/Proposed |
