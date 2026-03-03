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

Implement a **detection journal** as the single source of truth for git repos found in Syncthing-managed folders. The journal feeds both Syncthing (exclusion via `.stglobalignore`) and wsync/Unison (inclusion). Exclusion patterns propagate to all machines via Syncthing itself.

### Detection journal

A file at `~/.config/wsync/detected-repos` records every git repo found in Syncthing territory, with metadata (path, detection timestamp, machine). Both downstream consumers read from this journal:

- **Syncthing:** Journal entries are written to `.stglobalignore` files (one per Syncthing folder). Because `.stglobalignore` is a regular file (not `.stignore`), Syncthing syncs it to all devices, propagating exclusion patterns fleet-wide.
- **wsync:** Journal entries are added to the repo discovery list, giving repos outside `~/code/` the same branch-aware Unison sync treatment.

### Cross-machine propagation via `.stglobalignore`

The `.stignore` deployed by Ansible is static and includes a single `#include` directive:

```
// Static patterns (deployed by Ansible)
.git
.svn
.hg
.DS_Store
... (existing patterns) ...

// Auto-detected git repos (synced between devices)
#include .stglobalignore
```

The scanner writes ONLY to `.stglobalignore`. This file is a regular file inside each Syncthing folder (e.g., `~/Documents/.stglobalignore`), so Syncthing syncs it to Hub and to all other devices. When a device receives an updated `.stglobalignore`, the patterns take effect on the next scan.

**Known issue (Syncthing #7096):** Syncthing may not automatically rescan when a synced `#include`-d file changes. The fswatch process on each machine also watches for `.stglobalignore` changes and calls `POST /rest/db/scan` to force a rescan when the file is updated by sync from another device.

### Boot and wake: scanner runs before Syncthing

The scanner runs **before** Syncthing starts or reconnects, in two scenarios:

**Boot:**
- **Linux:** Scanner runs as a systemd oneshot with `Before=syncthing@.service`
- **macOS:** Scanner runs as a launchd agent with dependency ordering before Syncthing

**Wake from sleep:**
- **Linux:** The existing `syncthing-resume.sh` (installed to `/usr/lib/systemd/system-sleep/`) already restarts Syncthing on wake. The scanner is inserted before the restart.
- **macOS:** Scanner runs as a wake hook (via `sleepwatcher` or equivalent) before Syncthing reconnects.

In both cases, the scanner does a `find` sweep, writes the journal, and writes `.stglobalignore` directly to disk. Syncthing then starts (or restarts) with correct ignores already in place. This provides **zero race window for existing repos** at boot and wake — the most dangerous scenarios.

### Runtime: real-time filesystem watching

After boot, a persistent `fswatch` process monitors Syncthing-managed folders for two events:

1. **`.git/` directory creation:** A new git repo appeared. Scanner updates journal + `.stglobalignore` + calls `POST /rest/db/ignores` for immediate local effect.
2. **`.stglobalignore` modification:** Another machine detected a repo and its exclusion pattern arrived via sync. Scanner calls `POST /rest/db/scan` to force Syncthing to re-read the updated `#include`.

This uses the **same technology Syncthing does** (FSEvents on macOS, inotify on Linux), matching its detection speed.

### Unison is retained for code repos

Branch isolation remains non-negotiable for git repos. Unison syncs working tree files (excluding `.git/`) to branch-keyed directories on the hub. wsync is extended with `WSYNC_EXTRA_DIRS` support to handle repos discovered by the journal, not just those in `~/code/`.

### Syncthing remains continuous for user data

Syncthing continues running as a continuous daemon after the boot-delay scan. Its strengths — real-time filesystem watching, staggered versioning, NAT traversal, multi-device mesh — are the right fit for user data.

### Workflow analysis

Six workflows were traced to validate the architecture:

**Workflow 1 — Boot with existing repos on different branches:** SAFE. Scanner runs before Syncthing starts. `.stglobalignore` written directly to disk. Syncthing reads it on startup. Zero race window.

**Workflow 2 — `git clone` into ~/Documents/ while running:** SAFE. `git clone` creates `.git/` before writing working tree files. fswatch detects `.git/` and updates `.stglobalignore` before Syncthing processes the working tree. Millisecond race exists if FSEvents batches events, but even in the worst case, the files are from the default branch of a fresh clone — no branch garbling. `.stglobalignore` syncs to all devices, preventing other machines from pulling the files.

**Workflow 3 — `git init` on an already-synced directory:** SAFE. The directory was already syncing as regular user data. After `git init`, fswatch detects `.git/`, scanner writes `.stglobalignore`. The exclusion pattern syncs to all devices. Other machines stop syncing the directory. Stale copies on other machines are orphaned (no `.git/`, not a repo) — harmless debris, not corruption.

**Workflow 4 — Cross-machine propagation:** SAFE. `.stglobalignore` is a regular file synced by Syncthing. Machine A detects a repo → writes to `.stglobalignore` → Syncthing syncs it to Hub → Hub to Machine B → Machine B's fswatch detects `.stglobalignore` change → forces rescan → pattern takes effect. All machines converge on the same exclusion set.

**Workflow 5 — Wake from sleep with pending changes:** SAFE. The resume script restarts Syncthing after sleep. The scanner is inserted before the restart (same as boot sequence). Additionally, `.stglobalignore` may have been updated by other machines while this machine slept — on restart, Syncthing pulls the latest `.stglobalignore` and applies the patterns.

**Workflow 6 — Repo moved from ~/code/ to ~/Documents/:** SAFE. Same timing as Workflow 2 (fswatch detects `.git/` in the new location). wsync picks up the new location from the journal on its next run.

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

### Local-only `.stignore` writes (no cross-machine propagation)

Have the scanner write exclusion patterns directly to `.stignore` on the local machine only.

**Rejected because:** `.stignore` is local-only by design — it never syncs between devices. Machine A's detection is invisible to Machine B. This creates two failure modes: (1) orphaned working tree files on Machine B when Machine A excludes a repo, and (2) unsafe wake-from-sleep when Machine B pulls files from Hub that Machine A's scanner failed to prevent reaching Hub. The `.stglobalignore` approach closes both gaps by propagating exclusion patterns through Syncthing itself.

## Consequences

### Positive

- **Git repos can live anywhere.** Users don't need to think about sync tool boundaries. The system detects and routes automatically.
- **Zero race window at boot and wake.** The scanner runs before Syncthing starts or reconnects. The most dangerous scenarios (existing repos on different branches) are fully protected.
- **Near-zero race window at runtime.** fswatch matches Syncthing's detection speed. The millisecond FSEvents-batching window during fresh clones causes no practical damage (same branch on both machines).
- **Fleet-wide propagation.** `.stglobalignore` syncs through Syncthing itself, so Machine A's detection protects Machine B without any out-of-band coordination.
- **Single source of truth.** The journal provides auditability and a single debugging surface for both Syncthing exclusion and Unison inclusion.
- **Minimal architectural change.** Both tools continue doing what they do best. The journal, scanner, and `.stglobalignore` are additive, not disruptive.

### Accepted downsides

- **New daemon.** The fswatch scanner is a new long-running process that must be managed (systemd/launchd), monitored, and kept running. It watches for two event types: `.git/` creation and `.stglobalignore` modification.
- **Syncthing boot/wake delay.** The scanner must complete before Syncthing starts or reconnects. For a typical home directory, `find -name .git` takes < 1 second, but this adds a hard dependency to the boot and resume sequences.
- **Syncthing #7096 workaround.** Syncthing may not automatically rescan when a synced `#include`-d file changes. The fswatch process works around this by detecting `.stglobalignore` modifications and calling `POST /rest/db/scan`. If this Syncthing bug is fixed upstream, the workaround becomes unnecessary but harmless.
- **Orphaned files from pre-deployment.** Syncthing leaves already-synced files in place when a new ignore pattern is added. Repos damaged by Syncthing before the scanner was deployed require manual cleanup (`git checkout .`). This is a one-time migration concern, not ongoing.
- **Orphaned files on other machines.** When a new repo is detected and excluded, other machines may have already received some working tree files (without `.git/`). These are harmless debris (not git repos, no corruption risk) but should be cleaned up manually or via a `make clean-orphans` target.
- **EPIC-002 regression.** Implementation requires EPIC-002 to regress from Testing to Active for the scanner service and wsync expansion work.

### Follow-on work

- **JOURNEY-004 (Daily Multi-Machine Workflow):** New journey documenting the steady-state experience: "Put files anywhere. The system detects git repos and routes them to the right sync tool."
- **JOURNEY-003 update:** Add guidance for repos outside `~/code/` during machine migration.
- **wsync expansion:** Add `WSYNC_EXTRA_DIRS` support and qualified naming for repos outside `~/code/`.
- **Hub `.stglobalignore` handling:** Ensure the Hub server's Syncthing also reads `.stglobalignore` via `#include`, so the Hub stops relaying excluded files. The Hub doesn't run the scanner daemon but receives `.stglobalignore` updates via sync from spokes.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Adopted | 2026-03-03 | 52ee0c6 | Decision from SPIKE-008 research; skip Draft/Proposed |
