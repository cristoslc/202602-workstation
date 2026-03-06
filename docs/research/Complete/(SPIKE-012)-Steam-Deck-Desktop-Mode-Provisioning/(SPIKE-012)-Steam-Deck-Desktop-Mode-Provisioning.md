---
title: "SPIKE-012: Steam Deck Desktop Mode Provisioning"
artifact: SPIKE-012
status: Complete
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

### Thread 1: SteamOS Filesystem and Update Behavior

SteamOS uses an **A/B dual-root partition scheme**. Each slot has a ~5 GB read-only BTRFS root and a ~256 MB read-write EXT4 `/var`. A single shared `/home` partition (EXT4) spans both slots. Updates atomically write a new OS image to the inactive root slot and swap boot targets.

- `steamos-readonly disable` remounts the BTRFS root as read-write (`btrfs property set / ro false`). It does **not** survive reboots.
- `/etc` uses an **overlayfs** with the writable upper layer in `/var/lib/overlays/etc/upper`. Custom `/etc` changes persist across updates because the upper layer lives on the per-slot `/var`.
- **Pacman packages do NOT survive updates.** They write to `/usr` on the root partition, which is replaced wholesale.
- Writable areas: `/home` (always), `/var` (always, 256 MB, per-slot), `/etc` (via overlay). Many directories are bind-mounted from `/home/.steamos/offload/` including `/var/lib/flatpak`, `/var/lib/docker`, `/var/lib/machines`, `/root`, and `/nix`.

### Thread 2: Package Management

| Approach | Pre-installed | Survives Updates | CLI Dev Tools | Ansible Module |
|----------|---------------|------------------|---------------|----------------|
| Flatpak | Yes | Yes | Poor (GUI-focused) | `community.general.flatpak` (native) |
| Pacman | Yes (after unlock) | **No** | Excellent | `community.general.pacman` (native) |
| Distrobox | Yes (3.5+) | Yes | Excellent | Scriptable |
| Homebrew | No | Yes (`/home/linuxbrew`) | Good | Scriptable |
| **Nix** | No | **Yes (`/nix` Valve-supported)** | **Excellent** | Scriptable |

**Nix is the strongest option.** Since SteamOS 3.5, Valve explicitly added `/nix` to the preserved directories list. Single-user install (`--no-daemon`) is recommended. Nix home-manager provides declarative dotfile + package management. The Determinate Systems installer handles SteamOS-specific quirks automatically.

### Thread 3: Ansible Connectivity and Facts

- **SSH**: sshd ships pre-installed but **disabled**. Enable with `sudo systemctl enable sshd --now` after setting a password for the `deck` user. May need re-enabling after OS updates.
- **Python 3**: Pre-installed (3.10.x). Satisfies Ansible's managed-node requirement. No pip by default.
- **CRITICAL: `ansible_os_family` is wrong.** Ansible's `OS_FAMILY_MAP` maps `SteamOS` to `Debian` (a holdover from SteamOS 1.x/2.x which were Debian-based). SteamOS 3 is Arch-based. Never use `ansible_os_family` for package manager selection. Always use:
  ```yaml
  when: ansible_distribution is search("SteamOS")
  ```
- The `ansible_distribution` string has changed across Ansible versions (from `"Steamos"` to `"SteamOS GNU/Linux"`). Use `is search("SteamOS")` rather than exact equality.

### Thread 4: Dotfile and Config Compatibility

- **`/home` persists** across updates. GNU Stow symlinks work normally. Stow itself must be installed via Nix/Homebrew (not pre-installed).
- **Shell**: Bash is default. Zsh installable via Nix. `chsh` changes may be lost on update (modifies `/etc/passwd` on root); configure Konsole profile to launch zsh instead.
- **Terminal**: Konsole ships with KDE Plasma desktop mode.
- **Pre-installed dev tools**: git, curl, bash, Python. **Missing**: gcc, make, base-devel, wget, stow.
- **KDE config**: Uses `kwriteconfig5/6` + INI files in `~/.config/`, NOT dconf. No Hammerspoon equivalent; use KWin Scripts (JavaScript) + xdotool/ydotool.
- **Existing community projects**: Multiple dotfile repos exist for Steam Deck, most using Nix or Distrobox.

### Go / No-Go Assessment

All three go criteria are met:

1. **Package installation**: Flatpak works under Ansible (`community.general.flatpak`) for GUI apps. Nix provides excellent CLI tool coverage and is Valve-supported for persistence. Distrobox is a viable alternative.
2. **Stow-based dotfiles**: Works without modification on `/home`.
3. **Update survival**: `/home` and `/nix` both persist. `/etc` overlay persists in `/var`. The only ephemeral zone is the root filesystem (`/usr`, `/bin`, `/lib`).

**Verdict: GO** — proceed to Epic under VISION-001.

### Recommended Epic Scope

A `steamos/` platform directory with:
- **Bootstrap**: Enable sshd, install Nix (single-user), install Stow via Nix
- **Platform detection**: `ansible_distribution is search("SteamOS")` conditional; never rely on `os_family`
- **Package management**: Flatpak for GUI apps, Nix for CLI tools (no pacman in managed roles)
- **Dotfiles**: Existing stow-based deployment, with zsh launched via Konsole profile
- **Keybindings**: KWin Scripts + `kwriteconfig6` instead of Hammerspoon/dconf
- **Excluded roles**: Homebrew (macOS), macOS defaults, Raycast, and all macOS-only roles
- **Shared roles that apply**: git, terminal (Konsole config), shell (bash/zsh), text-expansion (Espanso has a Linux flatpak), backups (restic), secrets-manager

### Open Questions for Epic

- Should the Epic depend on Nix, making it a hard requirement? Or offer Distrobox as a fallback?
  - Depend on nix, but bootstrap it if Steam Deck detected. Do not rely on Nix for other environments.

- Does the Ansible `os_family` bug warrant an upstream PR to fix the SteamOS 3 mapping?
  - No, figure out after fault-tolerant solution.

- Should KDE keybinding management be a new cross-cutting concern (currently the keyboard role is Hammerspoon/dconf only)?
  - Yes, make a new SPIKE if needed.


## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-06 | 317a8f9 | Initial creation |
| Complete | 2026-03-06 | b407c2f | GO — Nix+Flatpak+Stow strategy viable; all go criteria met |
