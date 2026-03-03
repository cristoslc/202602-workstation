---
title: "JOURNEY-004: Daily Multi-Machine Workflow"
artifact: JOURNEY-004
status: Draft
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-vision: VISION-001
linked-personas:
  - PERSONA-001
depends-on:
  - EPIC-002
---

# JOURNEY-004: Daily Multi-Machine Workflow

## Persona

**PERSONA-001: Multi-Machine Developer** — A developer who works across 2-3 machines daily (desktop, laptop, and occasionally a remote server). They move between machines throughout the day, expecting their files and code to be available wherever they sit down.

## Goal

Work seamlessly across multiple machines throughout a normal day without thinking about sync tools, file locations, or branch state. Files saved on one machine appear on others. Code repos — wherever they live — sync with branch isolation and uncommitted work preserved.

## Steps / Stages

### Stage 1: Morning startup

The developer opens their laptop. It wakes from sleep or boots fresh. The system silently scans for git repos in user data folders, updates exclusion patterns, and starts Syncthing. By the time the developer opens a terminal, everything is in sync.

### Stage 2: Working on synced user data

The developer edits documents, saves screenshots, downloads files. These appear on other machines within seconds via Syncthing. No thought required — it just works, like iCloud or Dropbox.

### Stage 3: Working on code in ~/code/

The developer writes code, switches branches, leaves uncommitted changes. When they move to another machine, `wsync` has already synced the working tree to the hub, keyed by branch. They pick up right where they left off.

### Stage 4: Creating a repo outside ~/code/

The developer runs `git init` in `~/Documents/side-project/` or clones a repo into `~/Documents/HouseOps/`. The system detects the `.git/` directory within milliseconds, excludes the directory from Syncthing (preventing branch garbling), and registers it for Unison sync via wsync. The exclusion propagates to all machines via `.stglobalignore`.

### Stage 5: Switching machines

The developer closes the laptop and sits at the desktop. The desktop has already received `.stglobalignore` updates and user data changes. Code repos sync on the next wsync timer (5 minutes). The developer runs `wsync` manually if they want immediate sync. `wsync --status` shows all repos — from `~/code/` and from detected repos in user data folders.

### Stage 6: End of day

The developer closes all machines. No manual sync step, no "remember to push." Uncommitted code is on the hub. User data is on the hub. Tomorrow, any machine they open will have everything.

```mermaid
journey
    title Daily Multi-Machine Workflow
    section Morning Startup
      Wake laptop from sleep: 5: Developer
      Scanner runs before Syncthing: 5: System
      Syncthing catches up with hub: 5: System
      Open terminal, everything current: 5: Developer
    section User Data
      Edit documents, save files: 5: Developer
      Files appear on other machines: 5: System
    section Code in ~/code/
      Write code, switch branches: 5: Developer
      wsync syncs working tree to hub: 4: System
      Pick up work on another machine: 4: Developer
    section Repo Outside ~/code/
      git init in ~/Documents/: 4: Developer
      Scanner detects .git/ via fswatch: 5: System
      Excluded from Syncthing: 5: System
      Registered for wsync coverage: 4: System
      Exclusion propagates to fleet: 4: System
    section Switching Machines
      Close laptop, open desktop: 5: Developer
      Desktop has latest .stglobalignore: 5: System
      Run wsync for immediate code sync: 4: Developer
      wsync --status shows all repos: 4: Developer
    section End of Day
      Close all machines: 5: Developer
      All data on hub, no manual step: 5: System
```

## Pain Points

### wsync timer delay (score 4 — minor friction)

Code repos sync every 5 minutes via the wsync timer. When switching machines, the developer may need to wait or run `wsync` manually for immediate sync. This is a known trade-off: Unison's batch model doesn't support continuous watching as reliably as Syncthing.

### First-time detection propagation (score 4 — minor friction)

When a new repo is detected on Machine A, the `.stglobalignore` must sync to Machine B via Syncthing, and Machine B must rescan. This takes seconds but is not instantaneous. During this window, Machine B might briefly show the repo directory in its Syncthing state.

## Opportunities

- **`wsync --now` alias:** A shortcut that runs `wsync` immediately for the impatient machine-switcher.
- **Notification on detection:** A desktop notification when the scanner detects a new repo, confirming "HouseOps detected in Documents, excluded from Syncthing, added to wsync."
- **`wsync --status` dashboard:** Richer output showing sync recency, branch, and source directory for each repo.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | 871b26c | Initial creation |
