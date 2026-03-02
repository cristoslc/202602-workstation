---
title: "SPIKE-005: App Settings Sync Across Machines"
artifact: SPIKE-005
status: Active
author: cristos
created: 2026-02-25
last-updated: 2026-02-25
---

# SPIKE-005: App Settings Sync Across Machines

---

## Problem Statement

The workstation provisioning system installs 35+ roles across macOS and Linux. Many roles only handle **installation** — they don't capture or deploy the app's **configuration/settings**. When moving to a new machine, users must manually reconfigure these apps.

The system already has strong primitives:
- GNU Stow for symlinking dotfiles from git
- SOPS/age for encrypting sensitive config
- Ansible tasks for procedural settings (`osx_defaults`, `dconf`, `git_config`)
- Cross-platform layering (shared → platform → secrets)

The question is how to systematically extend these primitives to cover all roles.

---

## Current Coverage Audit

### Fully Managed (settings captured and deployed)

| Role | App(s) | Mechanism | Files/Settings |
|------|--------|-----------|----------------|
| **claude-code** | Claude Code | Stow | `shared/dotfiles/claude-code/.claude/settings.json` |
| **git** | git, gh, lazygit, delta | Stow + `git_config` | `.gitconfig`, `.gitignore_global`, platform git configs, user.name/email/signingkey via Ansible |
| **shell** | zsh | Stow | `.zshrc`, `.zshenv`, aliases, completion, functions, prompt, platform-specific `.zsh`, encrypted `secrets.zsh` |
| **shell** | direnv | Stow | `.config/direnv/direnvrc` |
| **terminal** | tmux | Stow | `.config/tmux/tmux.conf` |
| **stow** | GNU Stow (orchestrator) | Ansible | Backup, conflict resolution, layered stow execution |
| **editor** | VS Code | Stow + Ansible | `settings.json` per platform, `extensions.txt` installed via CLI |
| **text-expansion** | Espanso | Stow | `config/default.yml`, `match/base.yml` per platform, encrypted `match/private.yml` on Linux |
| **secrets-manager** | 1Password SSH agent | Stow | `.ssh/config`, `.ssh/config.d/1password-agent.conf` per platform |
| **macos-defaults** | macOS system prefs | Ansible `osx_defaults` | Dock (autohide, tilesize, mineffect), Finder (extensions, pathbar, view style), Keyboard (repeat rate, initial delay), Trackpad (tap-to-click, speed), Screenshots (location, format, shadow), Misc (save panel, network stores) |
| **desktop-env** | Cinnamon DE | Ansible `dconf` | Keyboard shortcuts (Super+V/E/Space for Vicinae), IBus hotkey overrides, screen-inhibit applet |
| **power** | Power management | Ansible `pmset` / `dconf` | macOS: display/system sleep, wake-on-LAN. Linux: Cinnamon power settings |
| **firewall** | ufw / socketfilterfw | Ansible | ufw rules (deny in, allow out, Tailscale subnets), macOS firewall enable |
| **hardware** | ThinkPad T14 Gen5 | Ansible templates | TLP charge thresholds, kernel params, suspend-then-hibernate, wakeup fixes, Wi-Fi module workaround |

### Partially Managed (placeholder or incomplete)

| Role | App | Current State | Gap |
|------|-----|---------------|-----|
| **terminal** | iTerm2 | Stow package exists with README only | Actual `com.googlecode.iterm2.plist` not committed (instructions say to export manually) |
| **editor** | VS Code | `settings.json` managed | `keybindings.json` and `snippets/` directory not captured |
| **backups** | Timeshift | Ansible template for `/etc/timeshift/timeshift.json` | Backblaze (macOS) settings not captured |
| **docker** | Docker | Credential store + log rotation via Ansible tasks | `~/.docker/config.json` and Docker Desktop preferences not in stow |

### Install-Only (no settings managed)

#### Amenable to Stow capture

These apps store text-based config files in known locations that can be added to stow packages.

| Role | App(s) | Config Location (macOS) | Config Location (Linux) | Notes |
|------|--------|------------------------|------------------------|-------|
| **node** | fnm, npm | `~/.npmrc` | `~/.npmrc` | Shared config; tokens go in secrets |
| **python** | uv | `~/.config/uv/uv.toml` | `~/.config/uv/uv.toml` | XDG-compliant, shared |
| **media** | VLC | `~/Library/Preferences/org.videolan.vlc/` | `~/.config/vlc/vlcrc` | Platform-specific paths |
| **file-transfer** | Filezilla | N/A (macOS uses Cyberduck) | `~/.config/filezilla/filezilla.xml` | Bookmarks may contain credentials → secrets |
| **lint-tools** | shellcheck, yamllint | Project-level configs | Project-level configs | Per-project, not per-machine — out of scope |

#### Amenable to Ansible task capture

These apps store settings via macOS `defaults` domains or Linux `dconf` keys, not plain files.

| Role | App(s) | macOS Domain / Linux dconf Path | Notes |
|------|--------|--------------------------------|-------|
| **launchers** | Raycast | Cloud-synced + local export | Raycast supports manual export; could script `raycast://` export or capture plist |
| **utilities** | Keka | `com.aone.keka` | Extraction preferences |

#### Cloud-Synced (out of scope for git-based sync)

These apps sync settings via their own cloud accounts. Capturing them in git would be redundant and fragile.

| Role | App(s) | Sync Mechanism |
|------|--------|----------------|
| **outlook** | Outlook | Microsoft Account |
| **excel** | Excel | Microsoft Account |
| **word** | Word | Microsoft Account |
| **powerpoint** | PowerPoint | Microsoft Account |
| **onedrive** | OneDrive | Microsoft Account |
| **edge** | Edge | Microsoft Account |
| **teams** | Teams | Microsoft Account |
| **secrets-manager** | 1Password | 1Password cloud |
| **communication** | Slack | Slack cloud |
| **communication** | Signal | Signal cloud (limited) |
| **calendar** | Dato, BusyCal | iCloud / account sync |
| **screenshots** | CleanShot X | Setapp cloud |
| **gaming** | Steam | Steam cloud |
| **vpn** | Tailscale | Tailscale cloud (device auth) |
| **vpn** | Surfshark | Surfshark cloud (account login) |
| **media** | Spotify | Spotify cloud |

#### Opaque / Not Practical for Git

| Role | App(s) | Why |
|------|--------|-----|
| **browsers** | Firefox, Chrome, Brave | Profile directories are large, binary, frequently changing. Use browser-native sync instead. |
| **stream-deck** | Stream Deck / OpenDeck | Profile databases — use vendor sync or manual export/import |
| **backups** | Backblaze | Cloud-managed backup schedule |

---

## Settings Taxonomy

Every app setting falls into one of these categories, each with a matching sync strategy:

### Category 1: Text Config Files (XDG / dotfiles)

**Strategy:** Add to stow packages in the correct layer.

- **Shared** (`shared/dotfiles/app/`): Identical on all platforms (e.g., `.gitconfig`, `.npmrc`)
- **Platform-specific** (`linux/dotfiles/app/`, `macos/dotfiles/app/`): Different paths or values per OS
- **Secret** (`*/secrets/dotfiles/app/`): Contains tokens/keys — SOPS-encrypt before committing

**Examples:** `.gitconfig`, `.npmrc`, `settings.json`, `tmux.conf`, `vlcrc`, `filezilla.xml`

### Category 2: macOS Defaults Domains (plist keys)

**Strategy:** Ansible `community.general.osx_defaults` tasks in the role's `darwin.yml`.

**Examples:** Dock autohide, Finder view style, app-specific preference keys

### Category 3: macOS Plist Files (complex/binary)

**Strategy:** Export with `defaults export` or copy from `~/Library/Preferences/`, store in `macos/dotfiles/app/` stow package.

**Caveat:** Binary plists produce opaque git diffs. Convert to XML with `plutil -convert xml1` before committing for readable diffs.

**Examples:** iTerm2 `com.googlecode.iterm2.plist`, Raycast export

### Category 4: Linux dconf Keys

**Strategy:** Ansible `community.general.dconf` tasks in the role's `debian.yml`.

**Examples:** Cinnamon keybindings, power manager settings, Nemo file manager preferences

### Category 5: Cloud-Synced

**Strategy:** Do nothing. Settings are managed by the vendor's cloud sync. The role only needs to install the app — login handles the rest.

**Examples:** 1Password, Slack, Microsoft 365 apps, Spotify, Steam

### Category 6: Opaque / Binary Databases

**Strategy:** Out of scope for git-based sync. Use vendor's export/import or backup/restore mechanisms manually.

**Examples:** Browser profiles, Stream Deck profiles, application caches

---

## Migration Workflow

### One-Time Export (from source Mac)

For each role with uncaptured settings:

1. **Identify** the config file location(s) on the source Mac
2. **Classify** as shared vs. platform-specific vs. secret
3. **Copy** the file into the repo at the correct stow package path:
   - Shared text config → `shared/dotfiles/<role>/` mirroring home dir structure
   - macOS-only text config → `macos/dotfiles/<role>/`
   - Secret config → `<layer>/secrets/dotfiles/<role>/` then SOPS-encrypt
4. **Convert** binary plists to XML: `plutil -convert xml1 <file>`
5. **Scrub** any embedded secrets (API keys, tokens) — either move to SOPS or replace with Ansible variable references
6. **Test** with `stow --no-folding --simulate -d <dir> -t ~ --restow <pkg>` to verify no conflicts
7. **Commit** and push

For `osx_defaults`-style settings, add tasks to the role's `darwin.yml` instead of stow.

### Ongoing Sync

After initial capture, the workflow for settings changes is:

1. Edit config on any machine (it's a symlink back to the repo)
2. `cd ~/workstation && git add -p && git commit && git push`
3. On other machines: `git pull && make apply ROLE=stow` (re-stow picks up changes)

For Ansible-managed settings (defaults/dconf), edit the task file and re-run `make apply ROLE=<role>`.

---

## Prioritized Gap List

Ordered by impact (settings that are most painful to reconfigure manually):

| Priority | Role | Gap | Effort |
|----------|------|-----|--------|
| **P1** | editor | VS Code `keybindings.json` + `snippets/` | Low — copy into existing vscode stow package |
| **P1** | terminal | iTerm2 plist export | Low — export plist, convert to XML, add to existing stow package |
| **P2** | node | `.npmrc` (registry, auth token placeholder) | Low — new shared stow package |
| **P2** | python | `~/.config/uv/uv.toml` | Low — new shared stow package |
| **P2** | docker | `~/.docker/config.json` (credential helpers, no tokens) | Low — new shared stow package, secrets for tokens |
| **P3** | launchers | Raycast settings export | Medium — requires manual Raycast export, then stow |
| **P3** | media | VLC preferences | Low — copy vlcrc into platform stow packages |
| **P3** | file-transfer | Filezilla site manager | Low — stow package, SOPS-encrypt if bookmarks contain credentials |
| **P4** | utilities | Keka preferences | Low — `osx_defaults` task or plist stow |
| **—** | browsers | Browser policies (not profiles) | Medium — JSON policy files deployed by Ansible |

---

## Alternatives Considered

### Mackup

A tool that relocates app config files to a cloud sync location and replaces them with symlinks. Supports 600+ apps.

**Rejected because:**
- Designed for cloud storage (Dropbox, iCloud), not git repos
- Only works on macOS (no Linux support)
- Overlaps with Stow — two symlink managers would conflict
- App database is community-maintained with varying quality

### Chezmoi

A dotfile manager with built-in templating, encryption, and multi-machine support.

**Rejected because:**
- Would replace the entire Stow infrastructure already in place
- Templating is powerful but adds complexity the current Ansible + Stow layering already handles
- Migration cost outweighs benefits for an established repo

### Syncthing / Resilio Sync

Peer-to-peer file sync between machines.

**Rejected because:**
- No version control (no git history, no rollback)
- Requires both machines to be online simultaneously
- Conflicts are hard to resolve for config files
- Doesn't integrate with the Ansible deployment model

### Nix Home Manager

Declarative home directory configuration.

**Rejected because:**
- Requires Nix ecosystem adoption (major migration noted in `docs/nixos-migration.md` as future work)
- Premature until feature set stabilizes (per AGENTS.md commit discipline note)

---

## Conclusion

**The best sync mechanism is the one already in place: git + Stow + Ansible.** No new tools needed. The work is:

1. Systematically capture uncaptured settings into stow packages (P1–P3 items above)
2. Add Ansible tasks for settings that aren't file-based (defaults domains, dconf keys)
3. Classify cloud-synced apps as out of scope (they sync themselves)

This keeps the architecture simple, the source of truth in git, and the deployment idempotent via `make apply`.

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Active | 2026-02-25 | 85c953e | Initial creation |
