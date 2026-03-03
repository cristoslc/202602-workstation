---
title: "SPIKE-008: Sync Boundary Enforcement"
artifact: SPIKE-008
status: Complete
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

### Critical discovery: the working tree problem is active, not theoretical

The current `.stignore` contains `.git`, which excludes `.git/` directories from Syncthing sync. **But it does NOT exclude the parent directory or working tree files.** This means for any git repo inside a Syncthing-managed folder (e.g., `~/Documents/HouseOps/`), all working tree files are actively being synced right now. If two machines are on different branches, Syncthing is silently garbling the working tree.

Compounding this: **Syncthing never deletes already-synced files when a new ignore pattern is added.** Files that were already synced are left on disk. This means any future protection mechanism must either:
1. Prevent damage before the first sync (pre-emptive), or
2. Include a cleanup/recovery procedure for repos that were already damaged

### Research area: Syncthing `.stignore` behavior

All questions answered favorably for programmatic management:

| Question | Answer | Source |
|----------|--------|--------|
| `.stignore` local-only? | **Yes.** Hardcoded into Syncthing; never synced between devices. | Syncthing docs |
| Already-synced files when ignored? | **Left in place.** Syncthing stops tracking but does not delete. | Jakob Borg (lead dev) confirmation |
| Safe to regenerate? | **Yes.** No system patterns embedded. Can overwrite entirely. REST API `POST /rest/db/ignores` replaces contents atomically. | Syncthing REST docs |
| Restart needed after changes? | **No.** Changes detected before next scan. REST API triggers immediate rescan. | Syncthing forum |
| Events API for directory detection? | **Yes.** `LocalChangeDetected` / `RemoteChangeDetected` events fire with `type: "dir"`. Available via `/rest/events/disk` long-polling endpoint. | Syncthing events docs |
| Programmatic ignore management? | **Yes.** `GET/POST /rest/db/ignores?folder=<id>` reads/writes ignore patterns per folder. | Syncthing REST docs |

**Key implication:** The Syncthing REST API (`POST /rest/db/ignores`) is the right integration point for a scanner. It replaces `.stignore` content atomically and triggers an immediate rescan, eliminating the delay of waiting for the next filesystem scan cycle.

### Research area: Unison scalability for user data

Unison is **not viable as a Syncthing replacement** for user data sync:

| Dimension | Finding | Verdict |
|-----------|---------|---------|
| 100GB / 100K files | Initial scan: ~30 minutes. Subsequent scans: seconds with `fastcheck` + warm cache. | Marginal |
| Memory usage | ~600MB RAM for large archives (loaded entirely into memory) | Concerning |
| Filesystem watching | `-repeat watch` + `unison-fsmonitor` works, but macOS requires a third-party adapter (not bundled). Known issues with cache update noise triggering spurious re-syncs. | Fragile |
| Continuous sync | Not a daemon; `-repeat watch` is a foreground loop. No process management, PID files, or service integration. | Poor |
| Topology | Strictly pairwise (2 roots per profile). Multi-machine requires star topology with separate profiles per pair. | Inferior to Syncthing |
| Large binary files | rsync-like block transfer over network, but full file rewrite on disk (no `--inplace`). Poor for files modified in-place. Fine for write-once media. | Acceptable for media |
| Conflict versioning | `-copyonconflict` places copies inline (not in a separate directory). No retention policy. Naming uses colons (breaks macOS). | Inferior to Syncthing |
| NAT traversal | None. Requires direct SSH access or VPN (Tailscale). | Inferior to Syncthing |

**Conclusion:** Approach C (Unison for everything) is eliminated. Syncthing is the right tool for user data: native continuous watching, staggered versioning with retention, NAT traversal, multi-device mesh capability. Unison excels at branch-aware code sync but cannot replace Syncthing for the user data use case.

### Research area: wsync multi-directory support

The current `wsync` implementation (319-line bash script) has three limitations relevant to this spike:

1. **Single root directory:** `WSYNC_CODE_DIR` defaults to `~/code`. No support for additional directories. SPIKE-006 design docs mention an optional `CODE_DIRS` array, but it was never implemented.

2. **One-level discovery:** `wsync_discover_repos()` scans `$CODE_DIR/*/` only — cannot find nested repos like `~/code/org/repo/`.

3. **Static profile:** Uses a single `code-sync.prf` Unison profile. Dynamic `-root` args are passed at invocation time. Profiles are plain `.prf` text files and can be generated programmatically.

**Extending wsync is straightforward:**
- `wsync_discover_repos()` can accept multiple directories (loop over an array)
- Each directory is scanned the same way (check for `.git/` in children)
- Unison profiles support multiple `path` directives within a single profile, or separate profiles per directory pair
- Hub server directory structure (`/srv/code-sync/<repo>/<branch>/`) needs no changes — repo names are already derived from directory basenames

**Estimated effort:** Small. Add `WSYNC_EXTRA_DIRS` env var or config file, loop over directories in the discover function, handle potential repo name collisions (e.g., `~/code/myrepo` vs `~/Documents/myrepo`).

### Research area: existing art

**No existing tool combines detection + exclusion + routing.** This is novel work.

| Tool / Pattern | What it does | Gap for SPIKE-008 |
|---------------|-------------|-------------------|
| Syncthing Tray | GUI for manual `.stignore` editing | No auto-detection |
| Facebook Watchman | Detects project roots by marker files (`.git`, `.watchmanconfig`) | Different purpose; good architectural pattern |
| fswatch | Cross-platform filesystem watcher (FSEvents on macOS, inotify on Linux) | Detection layer only; no Syncthing integration |
| reposcan / git-scan | CLI tools that find and report on git repos | Scanner only; no exclusion or routing |
| unison-gitignore | Translates `.gitignore` to Unison ignore flags | Different problem (ignore patterns, not repo detection) |
| chezmoi | Opt-in file management with `.chezmoiignore` | Inverted model (opt-in vs opt-out) |
| git-annex assistant | Watches filesystem + auto-syncs via git-annex | Closest architectural analogue but different purpose |

**Syncthing maintainers explicitly rejected auto-ignore for VCS directories** (GitHub issue #7215). Any solution must be external to Syncthing.

**Filesystem watching is viable on both platforms:**
- **macOS FSEvents:** Single recursive stream per root directory. Efficient; well within the 4096-stream limit.
- **Linux inotify:** One watch per directory. Modern kernels (5.11+) auto-adjust up to 1M watches. Each watch costs ~1KB kernel memory.
- **fswatch** abstracts both backends and is available via Homebrew and apt.

### Approach evaluation matrix

| Criterion | A (Pre-scan) | B (Event hook) | C (Unison all) | D+ (Hybrid + real-time) | E (Convention) |
|-----------|:---:|:---:|:---:|:---:|:---:|
| **Detection** (automatic) | PASS | PASS | N/A | PASS | FAIL |
| **Protection** (before damage) | PARTIAL | PARTIAL | PASS | PASS | FAIL |
| **Coverage** (repos outside ~/code/) | PASS | PASS | PASS | PASS | FAIL |
| **UX** (no sync tool knowledge) | PASS | PASS | PASS | PASS | FAIL |
| **Feasibility** | High | Medium | Low | High | High |
| **Complexity** | Low | High | Very High | Medium | Very Low |

**Why D+ achieves PASS on Protection:** The combination of delayed Syncthing start (boot) + real-time fswatch (runtime) closes the race window. At boot, the scanner runs before Syncthing starts — zero window for existing repos. At runtime, fswatch detects `.git/` creation at the same speed as Syncthing detects file changes — millisecond window for new repos, with near-zero practical damage because fresh clones share the same branch.

**Why A is PARTIAL on Protection:** Polling interval (5 minutes) loses the race against Syncthing's real-time filesystem watching every time.

**Why B is PARTIAL on Protection:** Syncthing's event API fires *after* the sync operation. The first sync of working tree files has already happened.

**Why C is eliminated:** Unison's 30-minute initial scan time for 100K files, 600MB memory footprint, lack of native continuous watching on macOS, and absence of conflict versioning make it unsuitable as a Syncthing replacement for user data.

**Why E is eliminated:** Fails three of four go/no-go criteria. Warnings don't prevent damage.

### Recommendation: Approach D+ (Hybrid with real-time detection and journal)

**Approach D is recommended**, refined with real-time filesystem watching and a centralized detection journal. The two-tool architecture is retained; each tool stays in its sweet spot.

#### Architecture: detection journal + `.stglobalignore` propagation

A centralized journal file (`~/.config/wsync/detected-repos`) is the authoritative registry of git repos found in Syncthing-managed folders. Both tools consume it, and exclusion patterns propagate fleet-wide via `.stglobalignore`:

```
fswatch detects .git/ creation in Syncthing folders
  + boot/wake find scan (catches existing repos)
  + .stglobalignore changes from other machines
         |
         v
  ~/.config/wsync/detected-repos   (journal)
         |
    +----+----+
    |         |
    v         v
Syncthing   wsync
(.stglobal-  (WSYNC_EXTRA_DIRS
 ignore,      for Unison sync)
 synced to
 all devices)
```

The `.stignore` deployed by Ansible is static. It includes a single `#include .stglobalignore` directive. The scanner writes ONLY to `.stglobalignore`, which is a regular file that Syncthing syncs to Hub and all other devices. This means Machine A's detection protects Machine B without out-of-band coordination.

**Syncthing #7096 workaround:** Syncthing may not automatically rescan when a synced `#include`-d file changes. The fswatch process on each machine also watches for `.stglobalignore` modifications (arriving from other devices) and calls `POST /rest/db/scan` to force a rescan.

#### Boot and wake: scanner runs before Syncthing

Syncthing must not start or reconnect before the scanner has run:

**Boot:**
1. Scanner runs as a oneshot service (`Before=syncthing@.service` on Linux, launchd dependency on macOS)
2. Scanner does a `find` sweep of all Syncthing-managed folders, writes journal and `.stglobalignore` directly to disk
3. Syncthing starts with correct ignores already in place

**Wake from sleep:**
1. The existing `syncthing-resume.sh` restarts Syncthing on wake. The scanner is inserted before the restart.
2. Scanner runs `find` sweep, updates journal and `.stglobalignore`
3. Syncthing restarts with current ignores

This provides **zero race window at boot and wake** — the most dangerous scenarios, where machines reconnect after being on different branches.

#### Runtime: real-time filesystem watching

After boot, a persistent `fswatch` process monitors Syncthing-managed folders for two event types:

1. **`.git/` directory creation:** A new repo appeared. Scanner updates journal + `.stglobalignore` + calls `POST /rest/db/ignores` for immediate local effect. `.stglobalignore` syncs to all devices.
2. **`.stglobalignore` modification:** Another machine detected a repo and its exclusion pattern arrived via Syncthing sync. Scanner calls `POST /rest/db/scan` to force Syncthing to re-read the updated `#include`.

The scanner uses the **same technology Syncthing does** (FSEvents on macOS, inotify on Linux) via `fswatch`. The remaining race window at runtime is milliseconds — and the practical damage during that window is near-zero because a freshly cloned repo has the same branch on both machines, and `.stglobalignore` propagation prevents other machines from pulling the files.

**Why not poll every 5 minutes?** Syncthing's filesystem watcher detects changes within milliseconds. A 5-minute scanner would always lose the race. A 5-second scanner would usually lose. Only real-time filesystem watching matches Syncthing's detection speed.

#### wsync multi-directory support

Extend wsync to discover and sync repos from the journal:

1. `wsync_discover_repos()` reads `~/.config/wsync/detected-repos` in addition to scanning `$WSYNC_CODE_DIR`
2. Repos outside `~/code/` get the same branch-aware Unison sync treatment
3. Name collisions handled with qualified names (e.g., `documents--HouseOps` on the hub)

#### Safety net: `make verify`

A `make verify` target warns about git repos in Syncthing folders. This provides a manual check for situations where the scanner isn't running (e.g., first install before the timer is set up).

#### Formal decision

This recommendation is formalized in **ADR-006: Git Repo Detection Journal with Sync Boundary Enforcement**.

### Impact assessment

**EPIC-002 (Sync User Folders):** Will need to regress from Testing to Active when implementation begins. The scanner service and wsync expansion are new capabilities within EPIC-002's scope.

**JOURNEY-003 (Machine Migration):** Update step 4 (migrate code repos) to note that repos outside `~/code/` are auto-detected and handled.

**JOURNEY-004 (Daily Multi-Machine Workflow):** Recommended as a new journey to document the steady-state experience: "Put files anywhere. The system detects git repos and routes them to the right sync tool." This journey would cover the scanner's behavior, `wsync status` output, and what happens when a new repo is created in `~/Documents/`.

### Go / No-Go verdict

**GO** — Approach D+ satisfies all four go/no-go criteria fully. The combination of delayed Syncthing start + real-time fswatch closes the race window that made Protection only PARTIAL in the original Approach D. The two-tool architecture is validated; the boundary needs active enforcement via a detection journal rather than passive convention.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-03 | 7de6f50 | Initial creation |
| Active  | 2026-03-03 | 2ec5cad | Transitioned to Active for research |
| Complete | 2026-03-03 | b9e6d47 | Research concluded; recommends Approach D (Hybrid) |
