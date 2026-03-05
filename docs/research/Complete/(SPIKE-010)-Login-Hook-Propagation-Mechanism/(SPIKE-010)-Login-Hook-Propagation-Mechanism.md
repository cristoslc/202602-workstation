---
title: "SPIKE-010: Login-Hook Propagation Mechanism"
artifact: SPIKE-010
status: Complete
author: cristos
created: 2026-03-04
last-updated: 2026-03-05
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

**Decision: GO — launchd user agent (macOS) + systemd user timer (Linux)**

### Candidate comparison

| Criterion | launchd/systemd | Shell profile hook | Periodic timer |
|-----------|----------------|-------------------|----------------|
| Truly async | Yes — OS-managed, separate process lifecycle | Fragile — SIGHUP on terminal close, subshell gotchas | Yes |
| Runs once per login | Yes (`RunAtLoad` / `OnStartupSec`) | No — fires on every `zsh --login` | No — schedule-based |
| Stow conflict | None — writes to `~/Library/LaunchAgents/` or `~/.config/systemd/user/` | **Conflicts** — `lineinfile` in `~/.zprofile` fights stow-managed dotfiles | None |
| Failure logging | Built-in (`StandardOutPath` / `journalctl --user`) | Manual redirect, silent on failure | Built-in |
| Ansible deploy | Template + enable module | `blockinfile` with markers (fragile idempotency) | Template + enable |
| Per-machine disable | Host var or sentinel file | Host var or sentinel file | Host var |

The shell profile hook was eliminated by the stow conflict — this repo manages dotfiles via stow, and Ansible-injected lines in `~/.zprofile` would fight the stow-managed copy.

### Recommended architecture

```
scripts/propagate.sh                    # Shared script (both platforms)
  - Check sentinel: ~/.workstation-no-propagate
  - Lock file: ~/.local/run/workstation-propagate.lock (flock)
  - git fetch origin main
  - If HEAD == origin/main: exit 0 (nothing to do)
  - git pull --ff-only || { log warning "branches diverged"; exit 0 }
  - Write status to ~/.local/state/workstation-propagate-status
  - Notify (osascript on macOS, notify-send on Linux)

shared/roles/propagation/templates/
  com.workstation.propagate.plist.j2     -> ~/Library/LaunchAgents/
  workstation-propagate.service.j2       -> ~/.config/systemd/user/
  workstation-propagate.timer.j2         -> ~/.config/systemd/user/
```

### Design decision for STORY-010: pull-only + notify

`make apply` currently requires interactive sudo (`read -rsp "BECOME password:"`). Rather than introducing unattended privilege escalation, the recommended starting point is:

1. **Auto-pull** upstream changes via `git pull --ff-only`
2. **Notify** the user that changes are available
3. **Defer** `make apply` to a manual step

This can be enhanced later with a `make apply-unattended` target if needed.

### launchd gotchas

- Plist does not expand `~` — use absolute paths via Ansible `{{ ansible_user_dir }}`
- After Ansible deploys the plist, it must be loaded via `launchctl bootstrap gui/<uid>` (post-task handler)
- `community.general.launchd` module has a known bug (#896) with `~` expansion — use `command: launchctl` as workaround
- No shell environment — set PATH via `EnvironmentVariables` in plist or use absolute paths in script
- `ThrottleInterval` throttles jobs exiting in < 10 seconds (not an issue for git-pull jobs)

### systemd gotchas

- User systemd instance stops when last session closes — long `make apply` runs could be killed on SSH disconnect (mitigate with `loginctl enable-linger` if needed)
- Timer uses `OnStartupSec=30` to avoid racing with other login tasks

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | ea363f7 | Unblocks STORY-010 design; attached to EPIC-004 |
