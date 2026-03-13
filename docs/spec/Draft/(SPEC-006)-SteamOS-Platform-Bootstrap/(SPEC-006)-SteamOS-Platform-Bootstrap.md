---
title: "SPEC-006: SteamOS Platform Bootstrap"
artifact: SPEC-006
status: Draft
author: cristos
created: 2026-03-12
last-updated: 2026-03-12
parent-epic: EPIC-007
linked-research:
  - SPIKE-012
linked-adrs: []
depends-on: []
addresses: []
evidence-pool: ""
swain-do: required
---

# SPEC-006: SteamOS Platform Bootstrap

## Problem Statement

The provisioning engine supports macOS and Linux Mint but has no SteamOS target. A Steam Deck in desktop mode requires a distinct bootstrap path: SSH enablement, Nix installation (the only update-safe CLI package manager), Stow via Nix, and a platform detection pattern that avoids Ansible's broken `os_family` mapping. Without this foundation, no other Steam Deck provisioning is possible.

## External Behavior

**Inputs:**
- A Steam Deck in desktop mode with the `deck` user password set and network connectivity
- The workstation repo cloned to `/home/deck/.workstation` (or run remotely via SSH)

**Outputs:**
- `steamos/` platform directory: `steamos/site.yml`, `steamos/inventory.yml`, `steamos/ansible.cfg`, `steamos/group_vars/all.yml`
- A `steamos-bootstrap` role that:
  1. Enables and starts sshd (`systemctl enable sshd --now`)
  2. Installs Nix single-user via the Determinate Systems installer (idempotent — skips if `/nix` exists)
  3. Installs GNU Stow via `nix profile install nixpkgs#stow`
- `make apply` detects SteamOS and runs `steamos/site.yml` instead of `macos/site.yml` or `linux/site.yml`
- Platform detection pattern: `ansible_distribution is search("SteamOS")` — never `ansible_os_family`

**Preconditions:**
- Network access (for Nix installer download)
- `deck` user has sudo access (default on SteamOS)

**Postconditions:**
- sshd running and enabled
- `nix` command available in `$PATH`
- `stow` command available via Nix profile
- `steamos/site.yml` runs without errors on a fresh Steam Deck

## Acceptance Criteria

1. **Given** a fresh Steam Deck in desktop mode, **when** `make apply` is run from the cloned repo, **then** the steamos playbook executes (not macOS or Linux).
2. **Given** sshd is disabled (default), **when** the bootstrap role runs, **then** sshd is enabled and started.
3. **Given** Nix is not installed, **when** the bootstrap role runs, **then** Nix single-user is installed via Determinate Systems installer and `nix --version` succeeds.
4. **Given** Nix is already installed, **when** the bootstrap role runs, **then** the Nix installation step is skipped (idempotent).
5. **Given** Nix is installed, **when** the bootstrap role completes, **then** `stow --version` succeeds (installed via Nix).
6. **Given** the steamos playbook, **when** `ansible_facts` are gathered, **then** no role uses `ansible_os_family` for SteamOS branching — all use `ansible_distribution is search("SteamOS")`.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- **In scope:** `steamos/` directory scaffolding, bootstrap role, Makefile platform detection, platform detection pattern documentation.
- **Out of scope:** CLI tool installation beyond Stow (that's SPEC-007), GUI apps (SPEC-008), dotfile deployment (STORY-014), modifications to shared roles (SPEC-009).
- Nix is Steam Deck only — this spec must not introduce Nix to macOS or Linux Mint targets.
- The bootstrap role must be idempotent — safe to re-run after SteamOS updates re-disable sshd.

## Implementation Approach

1. Scaffold `steamos/` directory mirroring `macos/` and `linux/` structure.
2. Create `steamos-bootstrap` role with three task files: sshd, nix, stow.
3. Add SteamOS detection to Makefile's `apply` target.
4. Test: verify sshd enablement is idempotent, Nix install is idempotent, Stow is available post-bootstrap.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-12 | — | Created during EPIC-007 decomposition |
