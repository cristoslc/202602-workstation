# Architecture Overview

_Supporting document for [VISION-001: Workstation as Code](./\(VISION-001\)-Workstation-as-Code.md)_

This is a living description of the system's architecture. It describes *how the system works* holistically. Individual architectural *decisions* (choices between alternatives with rationale) are recorded as ADRs.

---

## Entry points

| Entry | Purpose | Flow |
|-------|---------|------|
| `setup.sh` | One-liner bootstrap (curl-able) | Minimal bash → Python TUI |
| `./setup.sh --bootstrap` | Skip welcome menu | Straight to bootstrap mode selection |
| `make apply ROLE=<name>` | Apply a single role | Ansible playbook with role filter |
| `make status` | Verification dashboard | Textual TUI, read-only |
| `make verify` | Headless verification | Exit 1 on failure (CI-friendly) |
| `scripts/workstation-status.py` | Headless verification script | No TUI, exit code signaling |

### setup.sh bootstrap sequence

```
setup.sh
 ├─ Detect platform (Darwin / Linux)
 ├─ Clone repo to ~/.workstation if not already in a repo
 ├─ Ensure python3 (Xcode CLT on macOS, apt on Linux)
 ├─ Install uv (fast Python package manager)
 ├─ Install sops + age (pinned versions, SHA-256 verified on Linux)
 └─ Hand off → uv run scripts/setup.py (Textual TUI)
```

Exit code 7 from the TUI signals the caller to reload the shell (for dotfile changes to take effect).

## Phase-based provisioning

Ansible playbooks are organized into numbered phases. Both platforms share the numbering scheme; each phase maps to a playbook file under `<platform>/plays/`.

| Phase | Playbook | Description |
|-------|----------|-------------|
| 0 | `00-system.yml` | System foundation — Homebrew (macOS), apt base packages (Linux), compilers, build tools |
| 1 | `01-security.yml` | 1Password + SSH agent, SOPS + age, firewall |
| 2 | `02-dev-tools.yml` | git, shell (zsh), Python (uv), Node (fnm), Docker, VS Code, terminal, lint tools |
| 3 | `03-desktop.yml` | Browsers, launchers, media, communication, calendar, screenshots, text expansion, Stream Deck |
| 4 | `04-dotfiles.yml` | GNU Stow symlink deployment (4 layers) |
| 5 | `05-gaming.yml` | Steam, entertainment |
| 6 | `06-bureau-veritas.yml` | Compliance and monitoring (optional) |
| 8 | `08-sync.yml` | Syncthing, Unison, backups |

Phases are selectable in the TUI bootstrap screen. Each phase is idempotent — running it twice produces no changes on the second pass.

## Role organization

Roles are organized by **capability**, not by tool name. Each role handles both macOS and Linux internally via platform-specific task includes (`darwin.yml`, `debian.yml`).

```
shared/roles/          ← 45+ cross-platform roles
  ├── git/             ← git + gh + lazygit + delta + signing
  │   ├── defaults/main.yml
  │   └── tasks/
  │       ├── main.yml       ← dispatcher
  │       ├── darwin.yml      ← macOS-specific
  │       └── debian.yml      ← Linux-specific
  ├── shell/           ← zsh + direnv + fzf + ripgrep
  ├── browsers/        ← Firefox, Brave, Chrome, daily-driver default
  ├── backups/         ← Restic + Backrest + Backblaze/Timeshift
  └── ...

macos/roles/           ← 3 macOS-only roles
  ├── homebrew/        ← Brewfile-based package management
  ├── macos-defaults/  ← Dock, Finder, keyboard system defaults
  └── mas/             ← Mac App Store CLI

linux/roles/           ← 5 Linux-only roles
  ├── base/            ← build-essential, ripgrep, fd, bat
  ├── system/          ← X11, release pinning
  ├── desktop-env/     ← Cinnamon keybindings, themes
  ├── dev/             ← gcc, pkg-config, headers
  └── hardware/        ← Drivers, firmware
```

### Selective application

Roles support fine-grained application via Make targets and Ansible tags:

- `make apply ROLE=git` — apply the entire git role (git + gh + lazygit + delta)
- `make apply ROLE=git TAGS=lazygit` — apply only the lazygit sub-task within git
- `make verify-role ROLE=git` — verify just git-related installations

## GNU Stow dotfile layering

Dotfiles are deployed via GNU Stow with `--no-folding` (file-level symlinks, never directory symlinks). Four layers are applied in order; later layers override or extend earlier ones.

```
Layer 1: shared/dotfiles/          ← Cross-platform base
           ├── zsh/   git/   tmux/   ssh/   direnv/   espanso/   claude-code/

Layer 2: shared/secrets/dotfiles/.decrypted/   ← Decrypted shared secrets
           └── espanso/   (SOPS-encrypted snippets)

Layer 3: <platform>/dotfiles/      ← Platform-specific overrides
           macOS: espanso/  git/  hammerspoon/  iterm2/  ssh/  zsh/
           Linux: espanso/  git/  ssh/  zsh/

Layer 4: <platform>/secrets/dotfiles/.decrypted/   ← Decrypted platform secrets
```

**Collision prevention:** No numeric prefixes. Each layer uses descriptive filenames (`aliases.zsh`, `functions.zsh`, `local.zsh`). `make check-collisions` verifies no two layers provide the same target path.

## Secrets management

### Architecture

```
.sops.yaml                          ← SOPS config: age public key, path rules
shared/secrets/vars.sops.yml        ← Encrypted shared variables
<platform>/secrets/vars.sops.yml    ← Encrypted platform variables
shared/secrets/dotfiles/            ← Encrypted dotfile packages
~/.config/sops/age/keys.txt         ← Private age key (never committed)
```

### Encryption flow

- **At rest:** All secrets age-encrypted via SOPS. Public repo is safe.
- **At edit time:** `make edit-secrets-shared` decrypts to `$EDITOR`, re-encrypts on save.
- **At apply time:** Ansible decrypts SOPS vars on-the-fly during playbook runs; dotfiles decrypted to `.decrypted/` directories (gitignored).
- **Cleanup:** `make clean-secrets` wipes all decrypted files, unstows secrets symlinks, truncates logs.

### Enforcement

Two pre-commit hooks ensure secret safety:

1. **SOPS MAC check** — verifies all `.sops.*` files contain a valid SOPS message authentication code (blocks accidental plaintext commits).
2. **Gitleaks** — scans all staged files for hardcoded secrets (API keys, tokens, passwords).

### Application settings (age-encrypted exports)

Personalized app settings that are too complex for SOPS variables are exported as age-encrypted blobs:

| App | Encrypted file | Import method |
|-----|---------------|---------------|
| iTerm2 | `macos/files/iterm2/iterm2.plist.age` | `defaults write` to point at stow-managed plist |
| Raycast | `macos/files/raycast/raycast.rayconfig.age` | Decrypt to temp file, `open` triggers import dialog |
| Stream Deck | `macos/files/stream-deck/streamdeck.backup.age` | Decrypt to temp file, `open` triggers restore dialog |
| OpenIn | `macos/files/openin/openin.plist.age` | Decrypt and copy to preferences |
| Espanso snippets | `shared/secrets/dotfiles/espanso/...raycast.yml.sops` | SOPS-encrypted, stowed to `~/.config/espanso/match/` |

## TUI screen flow

```
WelcomeScreen (main menu)
  ├─→ FirstRunSetupScreen        ← age keygen, GitHub setup, secrets, pre-commit hooks
  ├─→ BootstrapModeScreen        ← fresh / new-account / existing-account
  │     └─→ BootstrapPhaseScreen ← phase + role selection
  │           └─→ BootstrapPasswordScreen ← sudo password
  │                 └─→ BootstrapRunScreen ← live Ansible output + timer
  ├─→ VerifyScreen               ← tabbed verification dashboard
  ├─→ DataMigrationScreen        ← rsync pull from source host
  ├─→ EditDefaultsScreen         ← keybindings + export checklist
  ├─→ SecretsScreen              ← form-based SOPS variable editing
  ├─→ ImportSettingsScreen       ← checklist of app settings to import
  └─→ KeyResolveScreen           ← modal: resolve missing/invalid age key
```

The TUI detects repo state on launch and adjusts the menu: fresh repos show only "First-Run Setup"; personalized repos show the full menu with warnings for pending steps.

## Supply chain verification

All external downloads are cryptographically verified before installation.

### Binary downloads

The shared task `shared/tasks/download-and-verify.yml` implements:

1. Download artifact to temp file (3 retries, 5s delay)
2. Compute SHA-256 of downloaded file
3. Assert hash matches the pinned expected value
4. Export verified path for the calling role

Roles pin version + checksum in their defaults:

```yaml
lazygit_version: "0.59.0"
lazygit_sha256: "264283f40a40c899d702a..."
lazygit_url: "https://github.com/.../v{{ lazygit_version }}/..."
```

### Package managers

- **Homebrew:** Installer commit pinned to a specific SHA
- **APT:** Repository GPG keys verified before adding sources
- **uv/sops/age in setup.sh:** Pinned versions with SHA-256 on Linux

### Version drift detection

`shared/tasks/version-check.yml` queries the GitHub API for latest releases and warns when pinned versions are outdated (respects `GITHUB_TOKEN` for rate limits).

## Testing infrastructure

| Layer | Tool | Location | Run with |
|-------|------|----------|----------|
| Shell unit tests | bats | `tests/bats/` (6 test files) | `make test-bats` |
| Python unit tests | pytest | `tests/python/` (13 test files) | `make test-python` |
| YAML lint | yamllint | `.yamllint.yml` | `make yamllint` |
| Shell lint | shellcheck | pre-commit + make | `make shellcheck` |
| Ansible lint | ansible-lint | `.ansible-lint` | `make ansible-lint` |
| Stow collisions | bats | `tests/bats/check-stow-collisions.bats` | `make check-collisions` |
| Cross-platform sync | bats | `tests/bats/check-synced-settings.bats` | `make check-sync` |
| All checks | make | — | `make check` (logs to `check.log`) |

### What's tested

- Stow filename collision detection across all 4 layers
- Cross-platform settings consistency (same roles produce equivalent configs)
- SOPS decryption round-trips
- TUI library functions (import/export, defaults, discovery)
- TUI screen interactions (integration tests with Textual pilot)
- Data migration progress tracking
- Template token replacement
- Variable scanning and secret collection

## Data sync architecture

```
Machine A (hub)  ◄──Syncthing──►  Machine B (spoke)
     │                                  │
     ├── ~/Documents/                   ├── ~/Documents/
     ├── ~/Pictures/                    ├── ~/Pictures/
     └── ~/Music/                       └── ~/Music/
                    (user data: Syncthing hub-and-spoke)

Machine A  ◄──Unison──►  Machine B
     │                        │
     └── ~/code/<repo>/       └── ~/code/<repo>/
                    (git working trees: Unison bidirectional)
```

- **Syncthing** handles user data (Documents, Pictures, Music, Videos, Downloads) in a hub-and-spoke topology.
- **Unison** handles git working trees with uncommitted changes — bidirectional sync that preserves uncommitted work across machines.
- **rsync** via `make data-pull SOURCE=<host>` for one-time bulk migration from an existing machine.
- **wsync** wrapper script + systemd timer / launchd agent for automatic Unison sync scheduling.
