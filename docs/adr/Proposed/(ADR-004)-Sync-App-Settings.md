# ADR-004: Sync App Settings via Expanded Stow + Ansible

**Status:** Proposed
**Date:** 2026-02-25
**Artifact:** ADR-004
**Research:** [sync-app-settings](../../research/Active/(SPIKE-005)-Sync-App-Settings/(SPIKE-005)-Sync-App-Settings.md)

## Context

The workstation provisioning system has 35+ Ansible roles that install applications across macOS and Linux. Most roles only handle **installation** — they don't capture or deploy the app's runtime settings. When provisioning a new machine or syncing preferences across machines, users must manually reconfigure many apps.

The system already has three primitives for managing settings:

1. **GNU Stow** — symlinks dotfile packages from git into `$HOME`
2. **SOPS/age** — encrypts sensitive config files at rest in git
3. **Ansible modules** — procedurally applies `osx_defaults`, `dconf`, `git_config`, etc.

These three cover 14 of 35+ roles today. The remaining roles are install-only.

## Decision

Expand the existing Stow + Ansible pattern to cover all roles with capturable settings. **No new tools or sync mechanisms.**

### Classification Framework

Every app setting is classified into exactly one category:

| Category | Sync Method | Example |
|----------|-------------|---------|
| **Text config file** | Stow package (shared or platform-specific) | `.npmrc`, `vlcrc`, `settings.json` |
| **Sensitive text config** | SOPS-encrypted stow package | `secrets.zsh`, espanso `private.yml` |
| **macOS defaults domain** | Ansible `community.general.osx_defaults` task | Dock autohide, key repeat |
| **macOS plist file** | Stow package (convert to XML first) | iTerm2 plist |
| **Linux dconf key** | Ansible `community.general.dconf` task | Cinnamon keybindings |
| **Cloud-synced** | No action (vendor handles sync) | 1Password, Slack, MS 365 |
| **Opaque/binary** | Out of scope | Browser profiles |

### Stow Package Placement Rules

1. Config identical on all platforms → `shared/dotfiles/<role>/`
2. Config differs by platform → `<platform>/dotfiles/<role>/`
3. Config contains secrets → `<layer>/secrets/dotfiles/<role>/` (SOPS-encrypted)
4. Stow package mirrors home directory structure (GNU Stow convention)

### Ansible Task Placement Rules

1. macOS `defaults write` settings → role's `tasks/darwin.yml`
2. Linux `dconf` settings → role's `tasks/debian.yml`
3. Use existing defaults/vars pattern for tuneable values

### Binary Plist Handling

Before committing macOS plist files to git:

```bash
plutil -convert xml1 <file>.plist
```

This produces human-readable XML diffs. The stow'd symlink serves the XML plist to the app, which still reads it correctly.

### Migration Workflow

**One-time export from source machine:**

1. Identify config file locations for the target role
2. Copy into the correct stow package path in the repo
3. For plists: convert to XML with `plutil`
4. For secrets: SOPS-encrypt with `sops --encrypt --in-place`
5. Test with `stow --simulate`
6. Commit and push

**Ongoing sync between machines:**

1. Edit config on any machine (it's a symlink into the repo)
2. Commit and push from that machine
3. Pull and re-stow on other machines: `git pull && make apply ROLE=stow`

### What's Explicitly Out of Scope

- **Cloud-synced apps** (1Password, Slack, MS 365, Spotify, Steam, Tailscale, Surfshark) — these sync via vendor accounts. Capturing their settings in git is redundant and fragile.
- **Browser profiles** — too large, too binary, too frequently changing. Use browser-native sync (Firefox Sync, Chrome Sync).
- **Per-project configs** (`.shellcheckrc`, `.yamllint`) — these belong in project repos, not the workstation repo.
- **Stream Deck profiles** — vendor-specific database format. Use manual export/import.

## Consequences

### Positive

- **No new tools** — uses only primitives already in the repo
- **Single source of truth** — all settings in git with full history
- **Idempotent deployment** — `make apply ROLE=stow` re-stows safely via `--restow`
- **Secret hygiene maintained** — SOPS/age encryption for any config containing tokens
- **Cross-platform parity** — platform-specific layering already handles macOS vs Linux differences
- **Incremental adoption** — roles can be migrated one at a time, prioritized by pain

### Negative

- **Manual export step** — initial capture from source machine requires per-role manual work
- **Binary plist diffs** — even as XML, large plists produce noisy diffs
- **No real-time sync** — changes require commit + push + pull (not instant like cloud sync)
- **Stow conflict risk** — adding new packages may conflict with files already present on target machines (mitigated by existing conflict resolution in `stow-packages.yml`)

### Neutral

- Cloud-synced apps remain outside the system. This is a feature, not a bug — it avoids duplicating vendor sync and reduces repo maintenance burden.
- The total number of stow packages will grow from 16 to ~25 as gaps are filled. This is well within Stow's capability.

## Alternatives Considered

See [research doc](../../research/Active/(SPIKE-005)-Sync-App-Settings/(SPIKE-005)-Sync-App-Settings.md#alternatives-considered) for detailed evaluation of Mackup, Chezmoi, Syncthing, and Nix Home Manager.
