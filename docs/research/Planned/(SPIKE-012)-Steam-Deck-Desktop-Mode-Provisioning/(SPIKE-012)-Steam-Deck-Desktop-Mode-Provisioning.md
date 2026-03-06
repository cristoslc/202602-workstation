---
title: "SPIKE-012: Steam Deck Desktop Mode Provisioning"
artifact: SPIKE-012
status: Planned
author: cristos
created: 2026-03-06
last-updated: 2026-03-06
question: "Can the existing workstation provisioning engine provision a Steam Deck in desktop mode, and what platform-specific adaptations are required?"
gate: Pre-MVP
risks-addressed:
  - SteamOS immutable root filesystem may block system-level provisioning
  - Arch-based package management (pacman/flatpak) differs from current Debian/Homebrew targets
  - SteamOS updates may reset system-level changes
depends-on: []
---

# SPIKE-012: Steam Deck Desktop Mode Provisioning

## Question

Can the existing workstation provisioning engine provision a Steam Deck in desktop mode, and what platform-specific adaptations are required?

Specifically:
1. **Filesystem mutability:** SteamOS ships with an immutable root (`/` is read-only). `steamos-readonly disable` unlocks it, but SteamOS updates re-lock and may overwrite changes. What provisioning strategies survive updates?
2. **Package management:** SteamOS is Arch-based but discourages direct pacman usage. Flatpak is the sanctioned install path. Can we use `community.general.flatpak` for app installation? What about CLI tools that aren't available as flatpaks?
3. **Dotfile deployment:** Home directory is writable. Does the existing stow-based dotfile approach work as-is?
4. **Ansible connectivity:** Can we SSH into desktop mode for remote provisioning, or must it be local-only?
5. **Platform detection:** How should Ansible identify SteamOS vs. standard Arch vs. Debian? What facts distinguish it?
6. **Scope boundary:** Which existing roles apply (git, terminal, shell, text-expansion, etc.) and which are irrelevant (Homebrew, macOS defaults, Raycast, etc.)?

## Go / No-Go Criteria

**Go** (proceed to Epic):
- At least one viable package installation strategy (flatpak and/or pacman) works under Ansible on SteamOS desktop mode
- Stow-based dotfile deployment works without modification
- A clear strategy exists for changes that survive SteamOS updates (even if limited to home-directory-only provisioning)

**No-Go** (abandon or defer):
- SteamOS actively prevents SSH access or Ansible execution in desktop mode
- The immutable root makes all system-level provisioning ephemeral with no workaround, AND flatpak coverage is too limited for useful app provisioning
- The platform requires so much divergence that it would be a separate project rather than a platform variant

## Pivot Recommendation

If system-level provisioning is not viable due to immutability:
- **Minimal pivot:** Scope the Epic to home-directory-only provisioning (dotfiles, shell config, git config, SSH keys, age keys) via a `steamos/` platform directory that skips all system-level roles. This is still valuable for consistent developer environment across machines.
- **Alternative:** Use Nix home-manager as a user-space package manager on SteamOS (avoids root entirely). Would require an ADR to evaluate the Nix dependency trade-off.

## Investigation Threads

### Thread 1: SteamOS Filesystem and Update Behavior
- Document the immutable root behavior: what `steamos-readonly disable` does, what survives updates
- Test whether `/etc/` changes persist across updates
- Identify the writable partitions and their mount points
- Check if `pacman` works after unlocking and whether installed packages survive updates

### Thread 2: Package Management on SteamOS
- Test `community.general.flatpak` module for app installation
- Inventory CLI tools available as flatpaks vs. those requiring pacman
- Evaluate Distrobox/toolbox as a container-based alternative for CLI tools
- Check if Homebrew on Linux works on SteamOS (it targets glibc, which SteamOS has)

### Thread 3: Ansible Connectivity and Facts
- Test SSH into desktop mode (does sshd ship? can it be enabled?)
- Run `ansible_facts` gathering and document the output (os_family, distribution, etc.)
- Determine the right conditional for SteamOS platform detection in roles

### Thread 4: Dotfile and Config Compatibility
- Test stow deployment to home directory
- Verify shell (zsh/bash), terminal emulator availability in desktop mode
- Check which existing shared roles work out of the box

## Findings

_To be populated during Active phase._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-06 | 317a8f9 | Initial creation |
