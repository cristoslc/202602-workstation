---
title: "SPIKE-008: Sync Boundary Enforcement"
artifact: SPIKE-008
status: Planned
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
question: "How should the system enforce the boundary between Syncthing (user data) and Unison (code repos) when git repositories exist outside ~/code/ and non-git projects exist inside it?"
gate: Pre-MVP
risks-addressed:
  - "Git repos in Syncthing folders get working tree garbling (branch mismatch → phantom diffs, sync-conflict files)"
  - "Convention-only boundary fails silently — user doesn't know something is wrong until git status is corrupted"
  - "wsync only auto-discovers repos in ~/code/ — repos elsewhere get no Unison coverage"
depends-on:
  - SPIKE-006
---

# SPIKE-008: Sync Boundary Enforcement

## Question

EPIC-002's sync architecture draws a hard boundary: Syncthing syncs user data folders (`~/Documents/`, `~/Pictures/`, etc.) and Unison syncs code repos (`~/code/`). The `.stignore` file excludes `.git/` from Syncthing, preventing git internals from syncing — but it still syncs the working tree files, which causes branch garbling when machines are on different branches.

**The problem:** This boundary is enforced by convention ("put code repos in `~/code/`"), not by the tools. In reality:

- `~/Documents/HouseOps/` is a git repo (personal project, lives in Documents by habit)
- `~/Documents/projects/some-experiment/` might have a `.git/` init
- Not everything in `~/code/` is a git repo (some are just directories of scripts)
- Users don't think about sync tools when choosing where to put a project

**What happens when the convention breaks:**
1. Syncthing syncs the working tree of `~/Documents/HouseOps/` across machines
2. Machine A is on `main`, Machine B is on `feature-branch`
3. Syncthing merges working tree files from both branches → garbled state
4. `.sync-conflict-*` files appear; `git status` shows phantom changes
5. User doesn't understand why their repo is broken

This spike evaluates approaches to detect and handle git repos in Syncthing territory, and asks whether the two-tool boundary is the right architecture at all.

## Go / No-Go Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Detection | Git repos in Syncthing folders are detected automatically (no manual inventory) | Relies on user remembering to register each repo |
| Protection | Detected repos are excluded from Syncthing sync before any damage occurs | Protection only kicks in after first sync conflict |
| Coverage | Repos outside `~/code/` get proper code-sync treatment (branch isolation, uncommitted work) | Repos outside `~/code/` are simply excluded with no sync at all |
| UX | User can put a git repo anywhere without thinking about sync tools | User must follow directory conventions or manually configure |

## Pivot Recommendation

If two-tool boundary proves untenable, consider:
- **Unison-for-everything:** Replace Syncthing entirely. Unison handles both user data and code, with different profiles/rules for git vs. non-git directories.
- **Accept the convention:** Document it clearly, add a `make verify` check that warns about repos in the wrong place, and don't try to fix it automatically. Simpler but less robust.

## Approaches to Evaluate

### A. Pre-scan service with dynamic `.stignore`

A background service (systemd timer / launchd agent) periodically scans Syncthing-managed folders for `.git/` directories. When found, it:
1. Adds the parent directory to `.stignore` (e.g., `HouseOps/`)
2. Optionally registers the repo with wsync for Unison coverage

**Pros:** Transparent to user. Repos can live anywhere. Existing tools unchanged.
**Cons:** Race condition between repo creation and next scan. `.stignore` grows unboundedly. Removing a repo doesn't auto-clean the ignore entry.

**Questions:**
- Can `.stignore` patterns be generated per-machine without Syncthing syncing the `.stignore` itself? (`.stignore` is local-only by default — yes)
- What's the scan interval vs. risk window? (If scan runs every 5 minutes, there's a 5-minute window where a new repo gets Syncthing'd)
- Does Syncthing need a restart/rescan after `.stignore` changes? (No — it picks up changes on next scan cycle)

### B. Syncthing pre-sync hook / filesystem watcher

Instead of periodic scanning, use Syncthing's event API or inotify/FSEvents to detect `.git/` directory creation in real-time and immediately update `.stignore`.

**Pros:** Near-zero race window. Reactive, not polling.
**Cons:** More complex. Syncthing's event API may not expose "new directory" events at the right granularity. inotify watch limits on large directory trees.

**Questions:**
- Does Syncthing emit events before or after syncing a new file? (After — so the first sync of a `.git/` directory's parent would still happen)
- Wait — `.git/` is already in `.stignore`. The issue is the working tree, not `.git/`. So the hook needs to detect "directory that contains `.git/`" and exclude the parent.

### C. Unison for everything (replace Syncthing)

Eliminate the two-tool boundary entirely. Use Unison for all sync, with different profiles:
- **User data profile:** Standard bidirectional sync for Documents, Pictures, etc. No `.git` awareness needed (no branch isolation for non-code).
- **Code profile:** Branch-isolated sync (current wsync behavior) for directories containing `.git/`.

**Pros:** Single tool. No boundary problem. Unison handles both use cases.
**Cons:** Unison is not designed for large media libraries (no streaming, no block-level deltas for binary files). Syncthing's continuous filesystem watching is better for "always in sync" UX. Unison requires a hub server for relay; Syncthing does NAT traversal natively.

**Questions:**
- Can Unison handle 500GB+ of user data across 5 folders with reasonable performance?
- Does Unison's lack of native file watching (relies on polling or fsmonitor) make it unsuitable for continuous sync?
- Would losing Syncthing's conflict versioning (`.stversions/`) be acceptable?

### D. Hybrid: Syncthing + dynamic exclusion + wsync expansion

Keep the two-tool approach but make it smarter:
1. **Scanner service** writes `.stignore` entries for detected git repos (Approach A)
2. **wsync expanded** to accept multiple code directories, not just `~/code/`
3. **wsync config** gets a `WSYNC_EXTRA_DIRS` list (e.g., `~/Documents/HouseOps`)
4. **Auto-registration:** Scanner adds detected repos to wsync's extra dirs list

**Pros:** Minimal architectural change. Each tool stays in its sweet spot. Git repos anywhere get proper treatment.
**Cons:** Two moving parts (scanner + wsync expansion). Config complexity increases.

### E. Convention + guardrails (simplest)

Don't try to auto-detect. Instead:
1. Add a `make verify` check: "WARNING: Git repos found in Syncthing folders: ~/Documents/HouseOps/"
2. Document the convention clearly in a journey or runbook
3. Add a git hook or shell alias that warns when `git init` is run outside `~/code/`

**Pros:** Simple. No new services. Convention is explicit.
**Cons:** Doesn't prevent the problem, only warns about it. User must act on the warning.

## Areas to Research

### Syncthing `.stignore` behavior
- Are `.stignore` files local-only (not synced)? → Yes, confirmed by Syncthing docs
- Can they be regenerated safely? (Overwrite vs. append)
- What happens to already-synced files when a new ignore pattern is added? (Left in place? Deleted?)

### Unison scalability for user data
- Benchmark Unison sync time for a 100GB `~/Documents/` folder with mixed file types
- Compare with Syncthing's steady-state sync performance
- Test Unison with 10,000+ files (typical Documents folder)

### wsync multi-directory support
- How hard is it to extend `wsync_discover_repos()` to scan multiple directories?
- Can the Unison profile handle multiple roots, or does each need a separate profile?
- Impact on hub server directory structure

### Existing art
- How does Syncthing Tray handle this? (Any "auto-ignore git repos" feature?)
- Does Unison have a "per-subtree profile" feature?
- How do other dotfile managers (chezmoi, yadm) handle this boundary?

## Related considerations

### Impact on journeys

If this spike recommends Approach A or D (auto-detection), it changes the daily workflow journey. A new **JOURNEY-004: Daily Multi-Machine Workflow** may be needed to document:
- "Put files anywhere. The system detects git repos and routes them to the right sync tool."
- "When you `git init` in `~/Documents/`, the scanner picks it up within 5 minutes."
- "Use `wsync status` to see which repos are being synced by Unison."

If Approach E (convention + guardrails), JOURNEY-003 should be updated with explicit guidance.

### Impact on EPIC-002

This spike's findings may require EPIC-002 to regress from Testing if the chosen approach requires implementation changes to the Syncthing or Unison roles.

## Findings

_To be populated during Active phase._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-03 | 7de6f50 | Initial creation |
