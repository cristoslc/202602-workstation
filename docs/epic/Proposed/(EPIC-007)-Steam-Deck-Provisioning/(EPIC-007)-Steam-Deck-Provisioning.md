---
title: "EPIC-007: Steam Deck Provisioning"
artifact: EPIC-007
status: Proposed
author: cristos
created: 2026-03-06
last-updated: 2026-03-06
parent-vision: VISION-001
success-criteria:
  - A fresh Steam Deck in desktop mode reaches a usable dev environment via `make apply` (dotfiles, shell, git, CLI tools)
  - Nix is bootstrapped automatically when SteamOS is detected; Nix is not introduced to any other platform
  - Flatpak GUI apps are installed declaratively via Ansible (`community.general.flatpak`)
  - Stow-based dotfile deployment works identically to macOS/Linux targets
  - All provisioned state survives SteamOS updates (nothing installed to ephemeral root filesystem)
  - Platform detection uses `ansible_distribution is search("SteamOS")`, never `ansible_os_family`
depends-on: []
addresses: []
---

# EPIC-007: Steam Deck Provisioning

## Goal / Objective

Extend the workstation-as-code provisioning engine to support the Steam Deck in desktop mode as a first-class platform target. The Steam Deck's immutable root filesystem and Arch-based SteamOS require a distinct provisioning strategy: Nix for CLI tools, Flatpak for GUI apps, and home-directory-only persistence. This epic delivers a `steamos/` platform directory that integrates with the existing Ansible role structure while respecting SteamOS's update-survival constraints.

SPIKE-012 confirmed viability: `/home` and `/nix` persist across updates, Stow works on `/home`, Flatpak has a native Ansible module, and SSH + Python 3 are available for remote provisioning.

## Scope Boundaries

**In scope:**
- `steamos/` platform directory with inventory, playbook, and platform-specific vars
- Bootstrap role: enable sshd, install Nix (single-user, Determinate Systems installer), install Stow via Nix
- Platform detection conditional: `ansible_distribution is search("SteamOS")` in all roles that need OS branching
- Nix package role: declarative CLI tool installation (git, zsh, stow, curl, age, sops, etc.)
- Flatpak role: GUI app installation via `community.general.flatpak`
- Dotfile deployment: existing Stow-based approach targeting `/home/deck`
- Shell configuration: zsh via Nix, launched from Konsole profile (not `chsh`)
- Shared roles that apply: git, terminal (Konsole config), shell (bash/zsh), text-expansion (Espanso flatpak), backups (restic via Nix), secrets-manager

**Out of scope:**
- KDE keybinding management (separate spike — SPIKE-013 or similar)
- Nix adoption on macOS or Linux Mint targets (Nix is Steam Deck only)
- Pacman-based package installation (ephemeral, not update-safe)
- Gaming Mode configuration (desktop mode only)
- Upstream PR to fix Ansible's `os_family` mapping for SteamOS 3
- Distrobox as a fallback (Nix is the hard dependency)

## Child Specs / Stories

_To be created during decomposition._

## Research Spikes

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| [SPIKE-012](../../../research/Complete/(SPIKE-012)-Steam-Deck-Desktop-Mode-Provisioning/(SPIKE-012)-Steam-Deck-Desktop-Mode-Provisioning.md) | Steam Deck Desktop Mode Provisioning | Complete | GO — all go criteria met |

## Key Dependencies

None — this epic adds a new platform target without modifying existing macOS or Linux provisioning paths.

## Design Decisions (from SPIKE-012)

1. **Nix is a hard dependency** for Steam Deck. Bootstrap it automatically when SteamOS is detected. Do not introduce Nix to other platforms.
2. **No upstream Ansible PR** for the `os_family` bug. Build fault-tolerant detection that doesn't rely on `os_family` at all.
3. **KDE keybindings are a cross-cutting concern** that warrants a separate spike. The current keyboard role (Hammerspoon/dconf) doesn't cover KDE; a new spike will evaluate KWin Scripts + `kwriteconfig6`.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-06 | b58ca4e | Created from SPIKE-012 GO verdict |
