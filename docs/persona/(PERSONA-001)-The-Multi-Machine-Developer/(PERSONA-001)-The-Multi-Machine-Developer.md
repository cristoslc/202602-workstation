---
title: "PERSONA-001: The Multi-Machine Developer"
status: Validated
author: cristos
created: 2026-02-27
last-updated: 2026-02-27
related-journeys:
  - JOURNEY-001
  - JOURNEY-002
  - JOURNEY-003
related-visions:
  - VISION-001
---

# PERSONA-001: The Multi-Machine Developer

## Archetype label

**The Multi-Machine Developer**

## Demographic summary

A senior software developer or technical lead, working solo or on a small team. Uses both macOS and Linux daily — typically a MacBook as a primary laptop and one or more Linux machines (desktop workstation, home server, or remote dev box). Comfortable with the terminal, shell scripting, and infrastructure tooling. Not a sysadmin by title, but acts as one for their own machines.

## Goals and motivations

- **Consistency across machines** — Wants the same shell, same keybindings, same tools, same git config on every machine. Switching between macOS and Linux should feel seamless.
- **Fast recovery** — If a machine dies or gets replaced, rebuilding should take minutes, not a weekend. The environment *is* the repo.
- **Security without friction** — Wants secrets encrypted and auditable, but doesn't want to think about key management on every commit. Encryption should be invisible in the daily workflow.
- **Version-controlled configuration** — Every change to the environment should be traceable. "Why is this tool installed?" and "when did this config change?" should be answerable from git history.
- **Minimal manual steps** — Automation over documentation. If a setup step can be scripted, it should be. Manual post-install checklists are a sign of incomplete automation.

## Frustrations and pain points

- **Setup drift** — Machines gradually diverge: one has a newer version of a tool, another has a stale dotfile, a third is missing a keybinding. Noticing the drift is worse than the drift itself — it surfaces at the worst times.
- **Dotfile fragility** — Hand-managed dotfiles conflict with system updates, break on platform differences, and are hard to diff across machines.
- **Secret sprawl** — API keys in `.env` files, tokens in shell history, SSH keys copied manually between machines. No single source of truth.
- **Platform-specific yak shaving** — Installing the same tool on macOS (Homebrew) and Linux (apt + manual binary) requires two different procedures, two different troubleshooting paths, and often two different config file locations.
- **The "new machine tax"** — Every hardware upgrade or OS reinstall costs a full day of setup, testing, and "I know I had this configured somewhere" archaeology.

## Behavioral patterns

- **Tinkers iteratively** — Adds tools and configs gradually over weeks, then wants to capture the current state into the repo. Rarely does a full from-scratch setup.
- **Trusts automation but verifies** — Runs `make verify` after bootstrap. Wants to see green checkmarks, not just "no errors."
- **Prefers declarative over imperative** — Would rather edit a YAML file and re-run the playbook than SSH in and run ad-hoc commands.
- **Treats machines as cattle, not pets** — Willing to wipe and rebuild rather than debug a deeply broken system. The repo is the pet; the machine is disposable.
- **Values selective application** — Doesn't always want to run the full bootstrap. Often applies a single role after tweaking its config.

## Context of use

- **When:** New machine setup (2-3 times per year), post-OS-upgrade rebuild, iterative tool additions (weekly), machine migration (when hardware changes).
- **Where:** Home office with multiple physical machines; occasionally provisioning a remote VPS or cloud instance.
- **How:** Clones the repo, runs `./setup.sh`, selects phases/roles in the TUI, waits for Ansible, verifies. For ongoing changes: edits a role, runs `make apply ROLE=<name>`, commits.
- **Devices:** MacBook Pro (primary), Linux desktop (secondary), occasional Linux server (headless, phases 0-2 only).

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Validated | 2026-02-27 | cf207f8 | Based on author's own usage pattern across 3+ machines |
