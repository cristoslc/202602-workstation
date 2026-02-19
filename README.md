# iac-daily-driver-environments

IaC-driven setup that makes Linux and macOS dev workstations fungible. Run `./bootstrap.sh` on a fresh install or an existing system and get a fully configured development environment.

- **Linux**: Mint 22 / Cinnamon / X11
- **macOS**: Homebrew + Raycast + opinionated defaults

## First Run

One-time setup to personalize the template and push to your own repo.

```bash
git clone https://github.com/TEMPLATE_OWNER/iac-daily-driver-environments.git ~/.workstation
cd ~/.workstation
./first-run.sh
```

The script self-installs its prerequisites (`age`, `sops`, `gum`, `gh`, `envsubst`) and walks you through:

1. **Generate age keypair** — creates `~/.config/sops/age/keys.txt`
2. **GitHub username + repo name** — personalizes clone URLs and config
3. **Encrypt secrets** — encrypts all placeholder secret files with your age key
4. **Pre-commit hooks** — installs the SOPS encryption check
5. **Create your GitHub repo** — via `gh repo create`, pushes initial commit
6. **Edit secrets** — guided walk-through to populate each secret file with real values

After first-run, the repo is yours. All subsequent machines clone from your repo.

## Quick Start

For bootstrapping a **second machine** from your own repo:

```bash
# Copy your age key to the new machine first
mkdir -p ~/.config/sops/age
# (paste or copy keys.txt into place)
chmod 600 ~/.config/sops/age/keys.txt

# Clone and bootstrap
git clone ${GITHUB_REPO_URL} ~/.workstation
cd ~/.workstation
./bootstrap.sh
```

The bootstrap wizard (powered by [gum](https://github.com/charmbracelet/gum)) walks you through:

1. **System type** — fresh install, existing system + new account, or existing system + existing account
2. **Role groups** — which phases to apply (system, security, dev tools, desktop, dotfiles)
3. **Confirmation** — summary of what will happen before Ansible runs

### Selective Runs

```bash
make apply ROLE=git             # Apply git + gh + lazygit + delta
make apply ROLE=gh              # Apply just the gh sub-task
make apply ROLE=browsers        # Apply all browsers + set daily driver
make apply ROLE=secrets-manager # Apply 1Password + SOPS
make apply ROLE=shell           # Apply zsh + direnv
make apply ROLE=file-transfer   # Apply Cyberduck/Filezilla
make lint                       # Run ansible-lint + yamllint
make status                     # Workstation status dashboard
make check-collisions           # Verify no stow filename conflicts
```

## Architecture

```
├── bootstrap.sh              OS dispatcher → platform bootstrap
├── Makefile                  Developer ergonomics (apply, lint, decrypt, status)
├── .sops.yaml                SOPS creation rules (age encryption)
├── shared/
│   ├── lib/wizard.sh         gum TUI wizard (sourced by both platforms)
│   ├── requirements.yml      Ansible Galaxy collections
│   ├── roles/                Function-based cross-platform roles
│   │   ├── git/              git + gh + lazygit + delta
│   │   ├── shell/            zsh + direnv
│   │   ├── secrets-manager/  1Password + SOPS/age
│   │   ├── terminal/         tmux + iTerm2 verification
│   │   ├── editor/           VS Code + extensions
│   │   ├── browsers/         Firefox + Brave + Chrome, daily driver default
│   │   ├── launchers/        Raycast (macOS) / Vicinae (Linux)
│   │   ├── communication/    Slack + Signal
│   │   ├── media/            Spotify + VLC
│   │   ├── vpn/              Tailscale + Surfshark
│   │   ├── backups/          Backblaze (macOS) / Timeshift (Linux)
│   │   ├── utilities/        Keka (macOS)
│   │   ├── file-transfer/    Cyberduck (macOS) / Filezilla (Linux)
│   │   ├── text-expansion/   Espanso (Linux) / Raycast snippets (macOS)
│   │   ├── python/           uv + global tools
│   │   ├── node/             fnm + LTS
│   │   ├── docker/           Docker Engine/Desktop
│   │   ├── claude-code/      Claude Code CLI
│   │   └── stow/             GNU Stow dotfile deployment
│   ├── dotfiles/             Cross-platform stow packages (zsh, git, tmux, ssh, ...)
│   └── secrets/              Encrypted shared vars + secret dotfiles
├── linux/
│   ├── bootstrap.sh          Linux entry point (apt prereqs → uv → Ansible)
│   ├── site.yml → plays/     Phase playbooks (security → dev → desktop → dotfiles)
│   ├── roles/                Linux-only roles (base, system, desktop-env, dev)
│   ├── dotfiles/             Linux stow packages
│   └── secrets/              Encrypted Linux vars + secret dotfiles
├── macos/
│   ├── bootstrap.sh          macOS entry point (Homebrew → uv → Ansible)
│   ├── site.yml → plays/     Phase playbooks
│   ├── roles/                macOS-only roles (homebrew, mas, macos-defaults)
│   ├── dotfiles/             macOS stow packages
│   └── secrets/              Encrypted macOS vars
├── docs/                     Detailed documentation
└── scripts/                  Linting, collision checks, status dashboard
```

### Role Organization

Roles are organized by **function** (what capability they provide), not by tool name. Each role handles both platforms internally via OS dispatch. This ensures:

- Adding a tool on macOS naturally prompts considering the Linux equivalent
- `make apply ROLE=<function>` runs everything related to that capability
- Sub-task tags allow running individual tools: `make apply ROLE=gh` runs only the gh sub-task within the git role

**Naming convention**: plural when multiple tools of the same type (`browsers`, `launchers`, `backups`), singular when one tool or concept (`git`, `shell`, `terminal`, `editor`).

### How the Layers Work

**Ansible** installs tools and configures the system. Shared roles use OS dispatch (`include_tasks: debian.yml` / `darwin.yml`). Platform roles handle OS-specific tools.

**GNU Stow** (`--no-folding`) manages dotfiles as file-level symlinks. Four layers, stowed in order:

1. `shared/dotfiles/` — cross-platform base
2. `shared/secrets/dotfiles/` — decrypted shared secrets
3. `<platform>/dotfiles/` — platform-specific
4. `<platform>/secrets/dotfiles/` — decrypted platform secrets

Collisions between layers are prevented by naming convention (not numeric prefixes):

| Layer | Example filename |
|---|---|
| Shared | `aliases.zsh`, `functions.zsh` |
| Platform | `linux.zsh`, `macos.zsh` |
| Secrets | `secrets.zsh` |
| Local (user, gitignored) | `local.zsh` |

### Composable Dotfiles

Every repo-managed config supports a local override file that is **never tracked by git**:

- `~/.config/zsh/local.zsh` — machine-specific shell config
- `~/.config/git/local.gitconfig` — machine-specific git settings (user.email, signing key)
- `~/.config/espanso/match/local.yml` — machine-specific text expansions

On existing systems, bootstrap backs up pre-existing dotfiles to `~/.workstation-backup/<timestamp>/` and migrates their content into the appropriate local override file.

### Bootstrap Modes

| Mode | System roles | Dotfiles | macOS defaults |
|---|---|---|---|
| Fresh install | Apply all | Replace everything | Apply unconditionally |
| Existing system, new account | Skip (system already configured) | Apply normally | Diff and confirm per category |
| Existing system, existing account | Skip unless opted in | Back up existing, migrate to local overrides | Diff and confirm per category |

## Secrets

All secrets encrypted with [SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age). The repo is public.

```bash
make edit-secrets-shared      # Edit shared encrypted vars
make edit-secrets-linux       # Edit Linux encrypted vars
make edit-secrets-macos       # Edit macOS encrypted vars
make decrypt                  # Decrypt to .decrypted/ (for debugging)
make clean-secrets            # Wipe .decrypted/ dirs
```

A pre-commit hook verifies all `*.sops.*` files contain SOPS metadata before commit.

See [docs/secrets.md](docs/secrets.md) for setup, key distribution, and rotation.

## Tools Managed

### Phase 1 — Security
`secrets-manager`: 1Password (+ SSH agent), SOPS + age

### Phase 2 — Development
`git`: git, gh, lazygit, delta · `shell`: zsh, direnv · `python`: uv · `node`: fnm · `docker`: Docker Engine/Desktop · `editor`: VS Code · `claude-code`: Claude Code CLI · `terminal`: tmux, iTerm2

### Phase 3 — Desktop
`browsers`: Firefox, Brave, Chrome · `launchers`: Raycast / Vicinae · `text-expansion`: Espanso · `communication`: Slack, Signal · `media`: Spotify, VLC · `vpn`: Tailscale, Surfshark · `backups`: Backblaze / Timeshift · `utilities`: Keka · `file-transfer`: Cyberduck / Filezilla

### Platform-only
**Linux**: `base` (build-essential, ripgrep, fd, bat, fzf, dust, duf, ...) · `system` (X11 check, release pin) · `desktop-env` (Cinnamon keybindings) · `dev` (gcc, pkg-config, headers)
**macOS**: `homebrew` (Brewfile) · `mas` (App Store: Amphetamine) · `macos-defaults` (Dock, Finder, keyboard, trackpad, screenshots)

## Documentation

- [Post-install manual steps](docs/post-install.md) — things that can't be automated
- [Adding a new tool](docs/adding-tools.md) — how to add roles and dotfiles
- [Secrets management](docs/secrets.md) — SOPS + age setup, workflow, rotation
- [Vicinae fallback](docs/fallback.md) — swap to Ulauncher + CopyQ if needed
- [NixOS migration](docs/nixos-migration.md) — future migration path

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| IaC tool | Ansible | Cross-platform, declarative roles, large ecosystem |
| Dotfiles | GNU Stow | Simple, no magic, file-level symlinks with `--no-folding` |
| Secrets | SOPS + age | Public repo safe, no GPG complexity, Ansible integration |
| Role organization | Function-based | Each role = one capability, handles both platforms internally |
| Shell | zsh | Default on macOS, widely supported on Linux |
| Python | uv | Fast, replaces pip + pyenv + virtualenv |
| Node | fnm | Fast, rust-based, cross-platform |
| Bootstrap UX | gum | Single binary, no dependencies, beautiful TUI |
| Ansible install | uv tool install | Avoids stale distro packages |
