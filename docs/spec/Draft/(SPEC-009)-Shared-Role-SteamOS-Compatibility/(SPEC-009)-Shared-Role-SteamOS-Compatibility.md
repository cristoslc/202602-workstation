---
title: "SPEC-009: Shared Role SteamOS Compatibility"
artifact: SPEC-009
status: Draft
author: cristos
created: 2026-03-12
last-updated: 2026-03-12
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

# SPEC-009: Shared Role SteamOS Compatibility

## Problem Statement

Shared roles (git, shell, terminal, text-expansion, backups, secrets-manager) contain platform conditionals that assume either macOS or Debian Linux. SteamOS is Arch-based but Ansible misidentifies it as Debian (`os_family: Debian`). Each shared role that applies to Steam Deck needs a SteamOS code path that installs dependencies via Nix or Flatpak instead of Homebrew/apt, and uses `ansible_distribution is search("SteamOS")` for detection.

## External Behavior

**Inputs:**
- SteamOS detected via `ansible_distribution is search("SteamOS")`
- Nix and Flatpak available (via SPEC-006, SPEC-007, SPEC-008)

**Roles requiring SteamOS conditionals:**

| Role | macOS path | Linux path | SteamOS adaptation |
|------|-----------|------------|-------------------|
| git | Homebrew | apt | Nix (git, gh, lazygit, delta already in SPEC-007 package list) |
| shell | Homebrew (zsh) | apt (zsh) | Nix (zsh); Konsole profile sets default shell instead of `chsh` |
| terminal | iTerm2 (Homebrew Cask) | validates terminal | Konsole config in `steamos/dotfiles/konsole/` |
| text-expansion | Espanso (Homebrew) | Espanso (apt/snap) | Espanso Flatpak (`org.espanso.Espanso`) |
| backups | Restic + Backrest (Homebrew) | Restic (apt) | Restic via Nix; Backrest optional (no launchd/systemd user service on SteamOS) |
| secrets-manager | 1Password (Homebrew Cask) | 1Password (apt repo) | Skip 1Password GUI; age + sops via Nix only |

**Constraints:**
- No `ansible_os_family` usage — SteamOS detection must use `ansible_distribution is search("SteamOS")`
- Shared roles must remain backward-compatible with macOS and Linux Mint
- SteamOS conditionals use Nix/Flatpak for package installation, not pacman

## Acceptance Criteria

1. **Given** the git role runs on SteamOS, **when** packages are needed, **then** it delegates to Nix (skips Homebrew/apt tasks).
2. **Given** the shell role runs on SteamOS, **when** zsh is configured, **then** zsh is installed via Nix and a Konsole profile is deployed (no `chsh`).
3. **Given** the terminal role runs on SteamOS, **when** it runs, **then** a Konsole profile is deployed to `~/.local/share/konsole/`.
4. **Given** the text-expansion role runs on SteamOS, **when** Espanso is needed, **then** it is installed via Flatpak.
5. **Given** the backups role runs on SteamOS, **when** restic is needed, **then** it is installed via Nix.
6. **Given** the secrets-manager role runs on SteamOS, **when** it runs, **then** age and sops are installed via Nix (1Password GUI is skipped).
7. **Given** any modified shared role runs on macOS or Linux Mint, **then** existing behavior is unchanged.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- **In scope:** Adding SteamOS conditionals to the 6 roles listed above. Konsole profile dotfile. Verifying no regression on macOS/Linux.
- **Out of scope:** KDE keybinding management (separate spike per EPIC-007), roles that don't apply to Steam Deck (Homebrew, macOS-defaults, Raycast, etc.), new role creation (use existing shared roles).
- The `chsh` command modifies `/etc/passwd` which is on the immutable root — Konsole profile launch is the only supported approach.

## Implementation Approach

1. For each of the 6 roles, add a SteamOS task file (e.g., `tasks/steamos.yml`) included conditionally.
2. Create `steamos/dotfiles/konsole/` with a Konsole profile that launches zsh.
3. Verify macOS and Linux paths are unchanged by running existing playbooks.
4. Test each role's SteamOS path with the SteamOS platform vars.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-12 | — | Created during EPIC-007 decomposition |
