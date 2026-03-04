---
title: "SPIKE-010: Login-Hook Propagation Mechanism"
artifact: SPIKE-010
status: Planned
author: cristos
created: 2026-03-04
last-updated: 2026-03-04
question: "What is the correct async mechanism (launchd agent, shell profile hook, or systemd timer) for pull-and-apply propagation that won't block login, handles failures gracefully, and is deployable via Ansible?"
gate: Pre-implementation
risks-addressed:
  - STORY-010 async execution design — login hook must not block shell, must handle diverged branches, must be per-machine disableable
depends-on: []
linked-research:
  - EPIC-004
---

# SPIKE-010: Login-Hook Propagation Mechanism

## Question

What is the correct async mechanism for automatic pull-and-apply propagation on login?

STORY-010 requires a hook that:
- Runs `git pull --ff-only && make apply` on the workstation repo
- Does not block interactive shell startup
- Handles diverged branches (skip + warn, don't loop)
- Can be disabled per-machine
- Works on macOS (launchd) and Linux (systemd)

Candidates:
1. **launchd agent / systemd timer** — runs on login event, fully async, managed by the OS
2. **Shell profile hook** (`~/.zprofile` / `~/.bash_profile`) — runs a backgrounded script, simple but fragile
3. **Cron / periodic timer** — not login-triggered but periodic, simpler failure model

Each has trade-offs around notification (how does the user know it ran?), failure visibility (where do errors go?), and deploy complexity (Ansible template vs. shell snippet).

## Go / No-Go Criteria

**Go (one candidate is clearly best):**
- The mechanism runs fully async — shell prompt appears immediately regardless of apply duration
- Failures are logged to a discoverable location (not just syslog)
- The mechanism can be deployed and removed via an Ansible role without manual steps
- The mechanism works on both macOS and Linux (or has a clean per-platform variant)

**No-Go (no candidate is viable):**
- All candidates either block login or have no failure notification path
- Ansible deployment of the mechanism requires platform-specific hacks that outweigh the benefit
- The propagation concept itself is flawed (e.g., `make apply` is not idempotent enough to run unattended)

## Pivot Recommendation

If no-go: Replace auto-propagation with a manual-trigger convenience command (`make sync` or `workstation pull`) that the user runs explicitly, plus a shell prompt indicator showing "upstream changes available." This gives visibility without the risks of unattended apply.

## Findings

_Pending investigation._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | ea363f7 | Unblocks STORY-010 design; attached to EPIC-004 |
