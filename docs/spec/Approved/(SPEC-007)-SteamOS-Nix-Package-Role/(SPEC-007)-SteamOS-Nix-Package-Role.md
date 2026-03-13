---
title: "SPEC-007: SteamOS Nix Package Role"
artifact: SPEC-007
status: Approved
author: cristos
created: 2026-03-12
last-updated: 2026-03-13
parent-epic: EPIC-007
linked-research:
  - SPIKE-012
linked-adrs: []
depends-on:
  - SPEC-006
addresses: []
evidence-pool: ""
swain-do: required
---

# SPEC-007: SteamOS Nix Package Role

## Problem Statement

SteamOS's immutable root filesystem means pacman-installed packages are wiped on every OS update. SPIKE-012 confirmed that Nix is the only CLI package manager whose installs persist (`/nix` is Valve-supported). The provisioning engine needs a role that declaratively installs CLI tools via Nix on SteamOS, analogous to the Homebrew role on macOS.

## External Behavior

**Inputs:**
- A list of Nix packages defined in `steamos/group_vars/all.yml` under a `nix_packages` variable
- Nix already installed (via SPEC-006 bootstrap)

**Outputs:**
- All packages in the `nix_packages` list installed to the user's Nix profile
- A `steamos-nix-packages` Ansible role that:
  1. Iterates `nix_packages` and runs `nix profile install nixpkgs#<pkg>` for each
  2. Is idempotent — skips already-installed packages
  3. Supports a `nix_packages_remove` list for uninstalling deprecated packages

**Default package list** (from SPIKE-012 scope):
`git`, `zsh`, `curl`, `wget`, `age`, `sops`, `restic`, `bat`, `eza`, `fd`, `fzf`, `ripgrep`, `jq`, `htop`, `tree`, `delta`, `lazygit`, `gh`

**Constraints:**
- Only runs when `ansible_distribution is search("SteamOS")`
- Must not modify anything outside `/nix` and `/home/deck`

## Acceptance Criteria

1. **Given** a Steam Deck with Nix installed, **when** the nix-packages role runs, **then** all packages in `nix_packages` are available in `$PATH`.
2. **Given** a package is already installed, **when** the role runs again, **then** the package is not reinstalled (idempotent).
3. **Given** a package is added to `nix_packages`, **when** the role runs, **then** only the new package is installed.
4. **Given** a package is listed in `nix_packages_remove`, **when** the role runs, **then** that package is removed from the Nix profile.
5. **Given** the role is run on macOS or Linux Mint, **then** it is skipped entirely.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- **In scope:** Nix profile package installation role, default package list, removal support.
- **Out of scope:** Nix installation itself (SPEC-006), Nix home-manager (future enhancement), Nix flakes, GUI apps (SPEC-008).
- No Nix channels or flake configuration — use `nixpkgs#<pkg>` direct references for simplicity.

## Implementation Approach

1. Create `steamos-nix-packages` role with a task loop over `nix_packages`.
2. Use `nix profile list` to check installed state before installing (idempotent).
3. Define default `nix_packages` in `steamos/group_vars/all.yml`.
4. Test: verify install, idempotency, removal, and platform guard.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-12 | — | Created during EPIC-007 decomposition |
| Approved | 2026-03-13 | — | ADR check clean; spec reviewed and approved for implementation |
